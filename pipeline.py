"""Automated pipeline: drains the unprocessed proposal queue in Supabase, running
the interactive skill's exact steps for each row without a human in the loop.

Entry point is run_once() (called by main.py, which the user's API trigger invokes).
"""

import json
import logging
import re

import config
from src import (
    drive_service,
    gmail_service,
    logo_service,
    notes_service,
    slides_service,
    slides_tailor,
    supabase_service,
)
from src.google_clients import GoogleClients

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

_FILE_ID_RE = re.compile(r"/(?:file/d|presentation/d|document/d|spreadsheets/d)/([a-zA-Z0-9_-]+)")
_OPEN_ID_RE = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")


def _resolve_file_id(link: str) -> str:
    for pattern in (_FILE_ID_RE, _OPEN_ID_RE):
        match = pattern.search(link or "")
        if match:
            return match.group(1)
    return (link or "").strip()


def _transcription_text(fields: dict, additional_notes: str) -> str:
    lines = [f"{k}: {v}" for k, v in fields.items() if k != "raw_transcript" and v]
    body = "\n".join(lines)
    if additional_notes and additional_notes.strip():
        body += f"\n\nAdditional notes:\n{additional_notes.strip()}"
    raw = fields.get("raw_transcript")
    if raw:
        body += f"\n\nRaw transcript:\n{raw}"
    return body


def _process_row(clients: GoogleClients, supabase, row: dict) -> None:
    drive, slides, gmail = clients.drive, clients.slides, clients.gmail
    row_id = row["id"]
    link = (row.get("demo_notes_link") or "").strip()
    additional = row.get("additional_notes") or ""

    if not link:
        supabase_service.mark_row_processed(supabase, row_id, "error", error_message="No demo_notes_link on the row.")
        log.error("Row %s has no demo_notes_link", row_id)
        return

    file_id = _resolve_file_id(link)

    # Step 1 — transcribe the notes
    notes = drive_service.download_file_bytes(drive, file_id)
    fields = notes_service.transcribe(notes["content_bytes"], notes["mime_type"], additional)
    missing = notes_service.missing_required_fields(fields)
    if missing:
        reason = f"Could not process — unclear/missing required field(s): {', '.join(missing)}."
        supabase_service.mark_row_processed(supabase, row_id, "error", error_message=reason)
        log.error("Row %s: %s", row_id, reason)
        return

    client_org = fields["client_org"]

    # Step 2 — client folder
    folder = drive_service.create_client_folder(drive, client_org)

    # Step 3 — transfer the notes file in + save the transcription
    drive_service.move_file_into_folder(drive, file_id, folder["folder_id"])
    drive_service.upload_file(
        drive, folder["folder_id"], f"{client_org} - Demo Notes.txt",
        _transcription_text(fields, additional).encode("utf-8"), "text/plain",
    )

    # Step 4 — copy the master template
    deck = drive_service.duplicate_template(
        drive, config.V2_TEMPLATE_ID, folder["folder_id"], f"{client_org} - Uncharted Ice Proposal"
    )

    # Steps 5-7 — inspect, tailor in place (highlight-safe), leave verbatim slides alone
    dump = slides_service.dump(slides, deck["file_id"])
    edits = slides_tailor.build_edits(fields, additional, dump)
    zero_finds = []
    if edits:
        result = slides_service.apply_edits(slides, deck["file_id"], edits)
        zero_finds = [r["find"] for r in result.get("replacements", []) if r["occurrences"] == 0]
        log.info("Row %s: %d/%d edits applied", row_id, result["total_occurrences"], len(edits))

    # Structural changes (Liv's feedback) — LAST, by objectId so deletions don't
    # shift each other: always drop the framework slide; keep only the bonus slides
    # ticked in the notes, adjusting the bonus intro's count/value.
    kept_bonuses = [b for b in config.BONUS_SLIDES.values() if fields.get(b["field"])]
    delete_ids = list(config.ALWAYS_DELETE_SLIDE_IDS)
    delete_ids += [b["slide_id"] for b in config.BONUS_SLIDES.values() if not fields.get(b["field"])]
    if not kept_bonuses:
        delete_ids.append(config.BONUS_INTRO_SLIDE_ID)
    elif len(kept_bonuses) == 1:
        value = kept_bonuses[0]["value"]
        try:
            slides_service.apply_edits(slides, deck["file_id"], [{
                "slide_id": config.BONUS_INTRO_SLIDE_ID,
                "find": "2 value-packed bonus gifts valued at more than $3,995",
                "replace": f"1 value-packed bonus gift valued at more than ${value:,}",
            }])
        except Exception:
            log.exception("Row %s: bonus-intro edit failed", row_id)
    for slide_id in delete_ids:
        try:
            slides_service.delete_slide(slides, deck["file_id"], slide_id)
        except Exception:
            log.exception("Row %s: failed to delete slide %s", row_id, slide_id)

    # Step 8 — swap the client logo (best-effort, always flagged)
    logo = logo_service.find_logo_url(client_org, fields.get("client_domain", ""))
    logo_replaced = False
    if logo["logo_url"]:
        try:
            res = slides_service.replace_logo(slides, deck["file_id"], logo["logo_url"], config.CLIENT_LOGO_IMAGE_IDS)
            logo_replaced = bool(res["replaced"])
        except Exception:
            log.exception("Row %s: logo swap failed", row_id)

    # QA notes (mirror the skill's report)
    qa = []
    if zero_finds:
        qa.append(f"{len(zero_finds)} tailoring edit(s) did not match the deck and were skipped — review the wording")
    if "client_org" in fields.get("unclear_fields", []):
        qa.append("the client name was unclear in the notes — confirm it and rename the folder/deck if needed")
    if not logo["logo_url"]:
        qa.append("no client logo could be guessed — add one manually")
    elif not logo_replaced:
        qa.append("a guessed client logo could not be applied — add one manually")
    else:
        qa.append(f"client logo was auto-guessed from '{logo['domain']}' (favicon) — verify it's correct and on-brand")

    status = "needs_review" if qa else "success"

    # Steps 10-11 — email Liv, mark processed
    body = (
        f"Hi Liv,\n\n"
        f"The Uncharted Ice proposal for {client_org} has been generated and is ready for review.\n\n"
        f"Proposal deck: {deck['view_url']}\n"
        f"Client folder: {folder['view_url']}\n\n"
        + ("Please double-check before sending:\n- " + "\n- ".join(qa) + "\n\n" if qa else "")
        + "— Automated by the Uncharted Ice proposal maker"
    )
    subject = f"Uncharted Ice proposal ready — {client_org}"
    try:
        gmail_service.send_email(gmail, config.NOTIFY_EMAIL, subject, body)
    except Exception:
        log.exception("Row %s: notification email failed (proposal still built)", row_id)

    supabase_service.mark_row_processed(
        supabase, row_id, status,
        error_message="; ".join(qa) if qa else None,
        proposal_link=deck["view_url"],
    )
    log.info("Row %s -> %s (%s)", row_id, deck["view_url"], status)


def run_once() -> None:
    clients = GoogleClients()
    supabase = supabase_service.get_client()

    rows = supabase_service.list_unprocessed(supabase)
    log.info("Found %d unprocessed row(s)", len(rows))

    for row in rows:
        try:
            _process_row(clients, supabase, row)
        except Exception as exc:
            log.exception("Row %s failed", row.get("id"))
            try:
                supabase_service.mark_row_processed(
                    supabase, row["id"], "error",
                    error_message=f"Unexpected error: {exc}",
                )
            except Exception:
                log.exception("Row %s: also failed to mark error", row.get("id"))
