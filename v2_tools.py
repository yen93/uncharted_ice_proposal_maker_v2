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
    python v2_tools.py replace-logo  <presentation_link_or_id> <public_image_url>
    python v2_tools.py thumbnails    <presentation_link_or_id> <1,2,3,...> <out_dir>
    python v2_tools.py email-proposal "<client name>" "<deck_url>" "<folder_url>"

All IDs may be passed as raw IDs or as full Google Drive/Slides URLs.
`email-proposal` sends to config.NOTIFY_EMAIL (default liv@myadventuregroup.com.au;
override with the NOTIFY_EMAIL env var).
"""

import json
import re
import sys

import config
from src import drive_service, gmail_service, slides_service
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


def cmd_replace_logo(clients, presentation_link, image_url):
    _emit(slides_service.replace_logo(
        clients.slides, _resolve_id(presentation_link), image_url, config.CLIENT_LOGO_IMAGE_IDS
    ))


def cmd_thumbnails(clients, presentation_link, slides_csv, out_dir):
    indexes = [int(x) for x in slides_csv.replace(" ", "").split(",") if x]
    _emit(slides_service.thumbnails(clients.slides, _resolve_id(presentation_link), indexes, out_dir))


def cmd_email_proposal(clients, client_name, deck_url, folder_url):
    subject = f"Uncharted Ice proposal ready — {client_name}"
    body = (
        f"Hi Liv,\n\n"
        f"The Uncharted Ice proposal for {client_name} has been generated and is ready for review.\n\n"
        f"Proposal deck: {deck_url}\n"
        f"Client folder: {folder_url}\n\n"
        f"Please review before sending — in particular double-check the client logo and any figures.\n\n"
        f"— Automated by the Uncharted Ice proposal maker"
    )
    _emit(gmail_service.send_email(clients.gmail, config.NOTIFY_EMAIL, subject, body))


COMMANDS = {
    "fetch-notes": (cmd_fetch_notes, 2),
    "make-folder": (cmd_make_folder, 1),
    "move-file": (cmd_move_file, 2),
    "copy-template": (cmd_copy_template, 2),
    "save-text": (cmd_save_text, 3),
    "dump-slides": (cmd_dump_slides, 1),
    "apply-edits": (cmd_apply_edits, 2),
    "replace-logo": (cmd_replace_logo, 2),
    "thumbnails": (cmd_thumbnails, 3),
    "email-proposal": (cmd_email_proposal, 3),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    handler, argc = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if len(args) != argc:
        print(f"'{sys.argv[1]}' expects {argc} argument(s), got {len(args)}.\n")
        print(__doc__)
        sys.exit(1)
    clients = GoogleClients()
    handler(clients, *args)


if __name__ == "__main__":
    main()
