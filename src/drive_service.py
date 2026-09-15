"""Drive operations for the v2 routine: client folder, moving the notes file
into it, duplicating the master template, and saving the transcription.

Adapted from v1's drive_service.py. The one behavioural change from v1:
`create_client_folder` names the folder with the *bare client name* (no year
suffix), per the v2 spec ("name the folder with the Client/Company Name").
"""

import io

from googleapiclient.http import MediaIoBaseUpload

import config

FOLDER_MIME = "application/vnd.google-apps.folder"


def _escape(value: str) -> str:
    return value.replace("'", "\\'")


def create_client_folder(drive, client_name: str) -> dict:
    """Creates (or reuses, on a rerun) a folder named exactly `client_name`
    under the master proposals folder. Returns {folder_id, folder_name, view_url}."""
    folder_name = client_name.strip()

    existing = (
        drive.files()
        .list(
            q=(
                f"'{config.PROJ_DRIVE_FOLDER_ID}' in parents "
                f"and mimeType = '{FOLDER_MIME}' "
                f"and name = '{_escape(folder_name)}' "
                f"and trashed = false"
            ),
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = existing.get("files", [])
    if files:
        folder_id = files[0]["id"]
        return {
            "folder_id": folder_id,
            "folder_name": folder_name,
            "view_url": f"https://drive.google.com/drive/folders/{folder_id}",
            "reused": True,
        }

    created = (
        drive.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": FOLDER_MIME,
                "parents": [config.PROJ_DRIVE_FOLDER_ID],
            },
            fields="id, name",
            supportsAllDrives=True,
        )
        .execute()
    )
    folder_id = created["id"]
    return {
        "folder_id": folder_id,
        "folder_name": folder_name,
        "view_url": f"https://drive.google.com/drive/folders/{folder_id}",
        "reused": False,
    }


def move_file_into_folder(drive, file_id: str, folder_id: str) -> dict:
    """Transfers an existing Drive file into `folder_id` by swapping its parents.

    Falls back to copying the file into the folder if the move fails (e.g. the
    source is shared-but-not-owned, so its parents can't be changed). Returns
    {file_id, view_url, moved} — `file_id` is the resulting file (the original on
    a move, a new copy on the fallback)."""
    meta = (
        drive.files()
        .get(fileId=file_id, fields="parents, name", supportsAllDrives=True)
        .execute()
    )
    previous_parents = ",".join(meta.get("parents", []))
    name = meta.get("name", "")

    try:
        drive.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()
        return {
            "file_id": file_id,
            "view_url": f"https://drive.google.com/file/d/{file_id}/view",
            "moved": True,
        }
    except Exception:
        copied = (
            drive.files()
            .copy(
                fileId=file_id,
                body={"name": name, "parents": [folder_id]},
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        new_id = copied["id"]
        return {
            "file_id": new_id,
            "view_url": f"https://drive.google.com/file/d/{new_id}/view",
            "moved": False,
        }


def duplicate_template(drive, template_id: str, folder_id: str, new_name: str) -> dict:
    """Copies the master template deck into the client's folder (copies
    everything). Returns {file_id, view_url}."""
    copied = (
        drive.files()
        .copy(
            fileId=template_id,
            body={"name": new_name, "parents": [folder_id]},
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    file_id = copied["id"]
    return {
        "file_id": file_id,
        "view_url": f"https://docs.google.com/presentation/d/{file_id}/edit",
    }


def download_file_bytes(drive, file_id: str) -> dict:
    """Downloads a Drive file's raw bytes. For Google-native files (Docs/Slides)
    that can't be downloaded directly, exports to PDF instead. Returns
    {content_bytes, mime_type, name, ext}."""
    meta = (
        drive.files()
        .get(fileId=file_id, fields="name, mimeType", supportsAllDrives=True)
        .execute()
    )
    name = meta.get("name", "notes")
    source_mime = meta.get("mimeType", "")

    if source_mime.startswith("application/vnd.google-apps."):
        # Native Google doc — export a viewable rendition.
        export_mime = "application/pdf"
        content = (
            drive.files()
            .export(fileId=file_id, mimeType=export_mime)
            .execute()
        )
        return {"content_bytes": content, "mime_type": export_mime, "name": name, "ext": ".pdf"}

    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    from googleapiclient.http import MediaIoBaseDownload

    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    ext = ""
    if "." in name:
        ext = name[name.rindex("."):]
    return {"content_bytes": buf.getvalue(), "mime_type": source_mime, "name": name, "ext": ext}


def upload_file(drive, folder_id: str, filename: str, content_bytes: bytes, mime_type: str) -> dict:
    """Uploads raw bytes (e.g. the transcription text) into a client's folder.
    Returns {file_id, view_url}."""
    media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype=mime_type)
    created = (
        drive.files()
        .create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    file_id = created["id"]
    return {"file_id": file_id, "view_url": f"https://drive.google.com/file/d/{file_id}/view"}
