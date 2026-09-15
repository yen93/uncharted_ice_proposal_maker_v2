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

# Object IDs of the CLIENT-logo image shapes in the master template (the SWIM
# logo on the cover + the right-hand logo in the footer lockup on content
# slides). Drive copies preserve object IDs, so these are stable across every
# generated deck and can be swapped deterministically for the new client's logo.
# The "My Adventure Group" logo (left of each footer lockup) is intentionally
# NOT here — it stays on every deck. If the master template is ever rebuilt from
# scratch, re-derive these with the image-geometry inspection in the project
# history (footer client logo sits at x≈1.98"; MAG at x≈0.88").
# NOTE: this replaces the client logo on every slide it appears, including the
# "verbatim" slides 4 & 8 — a wrong client logo there would be just as wrong.
CLIENT_LOGO_IMAGE_IDS = [
    "g3f6c7e6914d_0_0",   # cover (slide 1)
    "g3f6c7e6914d_0_1",   # slide 3 footer
    "g3f6c7e6914d_0_3",   # slide 4 footer
    "g3f6c7e6914d_0_5",   # slide 6 footer
    "g3f6c7e6914d_0_7",   # slide 7 footer
    "g3f6c7e6914d_0_9",   # slide 8 footer
    "g3f6c7e6914d_0_11",  # slide 12 footer
]

# The reviewer who is notified when a proposal is ready — always Liv, never the
# account owner. (The NOTIFY_EMAIL env override exists only to repoint the reviewer
# if the role ever changes; leave it unset in production so Liv is notified.)
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL") or "liv@myadventuregroup.com.au"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# --- Automated pipeline (main.py) only. The interactive skill needs none of these. ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# `... or "..."` (not .get(default)) so a blank OPENAI_MODEL= line in .env still
# falls back instead of sending an empty model string to the API.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "gpt-5.6-luna"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
# The queue the API trigger drains. Columns used: id, demo_notes_link,
# additional_notes, is_processed, status, error_message, proposal_link, processed_at.
SUPABASE_LOG_TABLE = "proposal_demo_notes_email_logs"

# Transcription fields that hard-block a run if missing (everything else is optional).
REQUIRED_OCR_FIELDS = ["client_org", "recommended_service", "summary"]

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
    # For the "proposal ready" notification email. The reused refresh token
    # (shared with v1) was already consented for gmail.send, so adding it here
    # needs no new OAuth flow. If you ever re-run oauth_setup.py, this scope is
    # included in the consent.
    "https://www.googleapis.com/auth/gmail.send",
]


def require(*names: str) -> None:
    """Raise a clear error if any of the named config values are unset."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise RuntimeError(
            f"Missing required configuration: {', '.join(missing)}. "
            f"Set them in {BASE_DIR / '.env'} (see .env.example)."
        )
