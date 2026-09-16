"""CLI the `make-uncharted-ice-proposal` skill shells out to. Each subcommand
does one Google operation and prints a JSON result to stdout, so the skill stays
declarative and every step is auditable.

Usage:
    python v2_tools.py fetch-notes   <drive_file_link_or_id> <out_path>
    python v2_tools.py make-folder   "<Client Name>"
    python v2_tools.py move-file     <file_link_or_id> <folder_id>
    python v2_tools.py copy-template <folder_id> "<deck name>"
    python v2_tools.py save-text     <folder_id> "<filename>" <local_text_path>
    python v2_tools.py dump-slides   <presentation_link_or_id>
    python v2_tools.py apply-edits   <presentation_link_or_id> <edits_json_path>
    python v2_tools.py delete-slide  <presentation_link_or_id> <slide_index_or_object_id>
    python v2_tools.py replace-logo  <presentation_link_or_id> <public_image_url>
    python v2_tools.py thumbnails    <presentation_link_or_id> <1,2,3,...> <out_dir>
    python v2_tools.py email-proposal "<client name>" "<deck_url>" "<folder_url>" [fathom_note] [additional_notes_note] [logo_note]
    python v2_tools.py queue-list
    python v2_tools.py queue-done    <row_id> <status> <proposal_link|-> <error|-> [has_fathom_notes|-] [tag|-]

All IDs may be passed as raw IDs or as full Google Drive/Slides URLs.
`email-proposal` sends to config.NOTIFY_EMAIL (default liv@myadventuregroup.com.au;
override with the NOTIFY_EMAIL env var). Its three optional trailing args are
human-readable one-liners appended to the email as a "Run summary" (whether Fathom
notes were found/used, whether the salesperson's additional_notes were applied, and
whether a client logo was found/swapped); pass "-" to omit one.

`queue-list` prints the unprocessed rows of the Supabase queue
(proposal_demo_notes_email_logs) as JSON [{id, demo_notes_link, additional_notes}].
`queue-done` marks one row processed: status is success|needs_review|error; pass
"-" for an empty proposal_link or error. The two optional trailing args record
`has_fathom_notes` (true/false) and a free-text `tag` (e.g. the matched Fathom
meeting title/id); pass "-" to leave either column unchanged.
"""

import json
import re
import sys

import config
from src import drive_service, gmail_service, slides_service, supabase_service
from src.google_clients import GoogleClients

_FILE_RE = re.compile(r"/(?:file/d|presentation/d|document/d|spreadsheets/d)/([a-zA-Z0-9_-]+)")
_OPEN_RE = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")
_FOLDER_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")


def _resolve_id(arg: str) -> str:
    """Extracts a Drive/Slides ID from a URL, or returns the arg unchanged if it
    already looks like a bare ID."""
    for pattern in (_FILE_RE, _FOLDER_RE, _OPEN_RE):
        match = pattern.search(arg)
        if match:
            return match.group(1)
    return arg


def _emit(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_fetch_notes(clients, drive_link, out_path):
    file_id = _resolve_id(drive_link)
    result = drive_service.download_file_bytes(clients.drive, file_id)
    with open(out_path, "wb") as f:
        f.write(result["content_bytes"])
    _emit({
        "file_id": file_id,
        "name": result["name"],
        "mime_type": result["mime_type"],
        "ext": result["ext"],
        "path": out_path,
        "bytes": len(result["content_bytes"]),
    })


def cmd_make_folder(clients, client_name):
    _emit(drive_service.create_client_folder(clients.drive, client_name))


def cmd_move_file(clients, file_link, folder_id):
    file_id = _resolve_id(file_link)
    _emit(drive_service.move_file_into_folder(clients.drive, file_id, _resolve_id(folder_id)))


def cmd_copy_template(clients, folder_id, deck_name):
    _emit(drive_service.duplicate_template(
        clients.drive, config.V2_TEMPLATE_ID, _resolve_id(folder_id), deck_name
    ))


def cmd_save_text(clients, folder_id, filename, local_text_path):
    with open(local_text_path, "rb") as f:
        content = f.read()
    _emit(drive_service.upload_file(
        clients.drive, _resolve_id(folder_id), filename, content, "text/plain"
    ))


def cmd_dump_slides(clients, presentation_link):
    _emit(slides_service.dump(clients.slides, _resolve_id(presentation_link)))


def cmd_apply_edits(clients, presentation_link, edits_json_path):
    with open(edits_json_path, encoding="utf-8") as f:
        edits = json.load(f)
    if isinstance(edits, dict) and "edits" in edits:
        edits = edits["edits"]
    _emit(slides_service.apply_edits(clients.slides, _resolve_id(presentation_link), edits))


def cmd_delete_slide(clients, presentation_link, slide_ref):
    _emit(slides_service.delete_slide(clients.slides, _resolve_id(presentation_link), slide_ref))


def cmd_replace_logo(clients, presentation_link, image_url):
    _emit(slides_service.replace_logo(
        clients.slides, _resolve_id(presentation_link), image_url, config.CLIENT_LOGO_IMAGE_IDS
    ))


def cmd_thumbnails(clients, presentation_link, slides_csv, out_dir):
    indexes = [int(x) for x in slides_csv.replace(" ", "").split(",") if x]
    _emit(slides_service.thumbnails(clients.slides, _resolve_id(presentation_link), indexes, out_dir))


def cmd_queue_list(clients):
    _emit(supabase_service.list_unprocessed(supabase_service.get_client()))


def _opt(value):
    """Treats "" / "-" as an omitted optional CLI argument."""
    return None if value in (None, "", "-") else value


def cmd_queue_done(clients, row_id, status, proposal_link, error_message,
                   has_fathom_notes="-", tag="-"):
    link = _opt(proposal_link)
    err = _opt(error_message)
    fathom_raw = _opt(has_fathom_notes)
    fathom = None if fathom_raw is None else fathom_raw.strip().lower() in ("true", "yes", "1", "t")
    tag_val = _opt(tag)
    supabase_service.mark_row_processed(
        supabase_service.get_client(), row_id, status, error_message=err, proposal_link=link,
        has_fathom_notes=fathom, tag=tag_val,
    )
    _emit({"row_id": row_id, "status": status, "proposal_link": link, "error_message": err,
           "has_fathom_notes": fathom, "tag": tag_val})


def cmd_email_proposal(clients, client_name, deck_url, folder_url,
                       fathom_note="-", additional_notes_note="-", logo_note="-"):
    subject = f"Uncharted Ice proposal ready — {client_name}"
    summary_lines = []
    if _opt(fathom_note) is not None:
        summary_lines.append(f"- Fathom meeting notes: {fathom_note}")
    if _opt(additional_notes_note) is not None:
        summary_lines.append(f"- Salesperson additional notes: {additional_notes_note}")
    if _opt(logo_note) is not None:
        summary_lines.append(f"- Client logo: {logo_note}")
    summary = ("\nRun summary:\n" + "\n".join(summary_lines) + "\n") if summary_lines else ""
    body = (
        f"Hi Liv,\n\n"
        f"The Uncharted Ice proposal for {client_name} has been generated and is ready for review.\n\n"
        f"Proposal deck: {deck_url}\n"
        f"Client folder: {folder_url}\n"
        f"{summary}\n"
        f"Please review before sending — in particular double-check the client logo and any figures.\n\n"
        f"— Automated by the Uncharted Ice proposal maker"
    )
    _emit(gmail_service.send_email(clients.gmail, config.NOTIFY_EMAIL, subject, body))


# Each value is (handler, min_args, max_args). min == max for fixed-arity commands;
# a wider max marks trailing optional arguments.
COMMANDS = {
    "fetch-notes": (cmd_fetch_notes, 2, 2),
    "make-folder": (cmd_make_folder, 1, 1),
    "move-file": (cmd_move_file, 2, 2),
    "copy-template": (cmd_copy_template, 2, 2),
    "save-text": (cmd_save_text, 3, 3),
    "dump-slides": (cmd_dump_slides, 1, 1),
    "apply-edits": (cmd_apply_edits, 2, 2),
    "delete-slide": (cmd_delete_slide, 2, 2),
    "replace-logo": (cmd_replace_logo, 2, 2),
    "thumbnails": (cmd_thumbnails, 3, 3),
    "email-proposal": (cmd_email_proposal, 3, 6),
    "queue-list": (cmd_queue_list, 0, 0),
    "queue-done": (cmd_queue_done, 4, 6),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    handler, min_argc, max_argc = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if not (min_argc <= len(args) <= max_argc):
        want = str(min_argc) if min_argc == max_argc else f"{min_argc}-{max_argc}"
        print(f"'{sys.argv[1]}' expects {want} argument(s), got {len(args)}.\n")
        print(__doc__)
        sys.exit(1)
    clients = GoogleClients()
    handler(clients, *args)


if __name__ == "__main__":
    main()
