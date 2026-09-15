"""Loads environment variables and project_vars.txt constants for the v2
interactive proposal routine.

v2 is deliberately small: no Gmail/Forms/OCR/Supabase/Fathom (all v1 concerns).
It only needs Drive + Slides API access and two fixed IDs — the master proposals
folder and the master template deck.
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

_FOLDER_ID_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")
_PRESENTATION_ID_RE = re.compile(r"/presentation/d/([a-zA-Z0-9_-]+)")


def _folder_id_from_link(link: str) -> str:
    match = _FOLDER_ID_RE.search(link)
    if not match:
        raise ValueError(f"Could not extract a Drive folder ID from: {link}")
    return match.group(1)


def _presentation_id_from_link(link: str) -> str:
    match = _PRESENTATION_ID_RE.search(link)
    if not match:
        raise ValueError(f"Could not extract a Slides presentation ID from: {link}")
    return match.group(1)


def _load_project_vars() -> dict:
    with open(BASE_DIR / "project_vars.txt", encoding="utf-8") as f:
        data = json.load(f)
    return data[0]


_PROJECT_VARS = _load_project_vars()

# The master "Proposals" folder every client folder is created under.
PROJ_DRIVE_FOLDER_ID = _folder_id_from_link(_PROJECT_VARS["proj_drive_link"])
# The v2 master template deck (the sales-specialist-quality Uncharted Ice deck).
V2_TEMPLATE_ID = _presentation_id_from_link(_PROJECT_VARS["template_link"])

# Slide map (1-indexed), per the v2 spec:
#   TAILOR   — retext client-specific wording in place, keep the design.
#   VERBATIM — leave completely untouched; the template already has them right.
TAILOR_SLIDES = [1, 2, 3, 5, 6, 7, 12]
VERBATIM_SLIDES = [4, 8, 9, 10, 11, 13]

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]


def require(*names: str) -> None:
    """Raise a clear error if any of the named config values are unset."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise RuntimeError(
            f"Missing required configuration: {', '.join(missing)}. "
            f"Set them in {BASE_DIR / '.env'} (see .env.example)."
        )
