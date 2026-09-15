"""Transcribe the demo-notes file (image/PDF) into structured fields via OpenAI
vision, folding in the row's free-text `additional_notes`.

This is the automated stand-in for what Claude does by eye in the interactive
skill's step 1. Adapted from ../uncharted_ice_proposal_maker/src/ocr_service.py
with a few extra fields the tailoring step needs (key_themes, investment_notes,
duration, client_domain).
"""

import base64

import config
from src import llm_client

EXTRACTION_TOOL = {
    "name": "extract_demo_notes",
    "description": "Structured fields transcribed from a sales demo-call notes page (often handwritten), for tailoring an Uncharted Ice proposal deck.",
    "input_schema": {
        "type": "object",
        "properties": {
            "client_org": {"type": "string", "description": "Client company/organisation name"},
            "contact_name": {"type": "string", "description": "Primary contact person at the client, if any"},
            "event_date": {"type": "string", "description": "Event/session date if mentioned (e.g. 'September 2026'), else empty string"},
            "recommended_service": {"type": "string", "description": "The service recommended (e.g. keynote, workshop, 3-day retreat, full-day session)"},
            "duration": {"type": "string", "description": "Session length / format if mentioned (e.g. '3-day retreat', 'full-day', '6hr', '2hr'), else empty"},
            "audience_size": {"type": "string", "description": "Audience/attendee size and who they are, if mentioned"},
            "location": {"type": "string", "description": "Delivery location or virtual/in-person, if mentioned"},
            "key_themes": {"type": "string", "description": "The key themes / learning objectives / values discussed (comma- or newline-separated as written)"},
            "investment_notes": {"type": "string", "description": "Any pricing/budget/investment figures or options mentioned (e.g. 'AU$18,500 for 3-day; $8,500 conference'), else empty"},
            "bonus_debrief_call": {"type": "boolean", "description": "True only if the 'Debrief Call' item in the notes' ADD BONUS VALUE checklist is ticked/checked"},
            "bonus_executive_x": {"type": "boolean", "description": "True only if the 'Executive X' item in the notes' ADD BONUS VALUE checklist is ticked/checked"},
            "summary": {"type": "string", "description": "1-3 sentence summary of the client's situation and goals"},
            "scope": {"type": "string", "description": "Notes on scope, program components, day-by-day breakdown, etc."},
            "client_domain": {"type": "string", "description": "Best guess of the client's website domain for a logo lookup (e.g. 'tilray.com'), else empty string"},
            "raw_transcript": {"type": "string", "description": "Best-effort full transcription of all text on the page"},
            "unclear_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of fields above that were illegible, ambiguous, or not present",
            },
        },
        "required": [
            "client_org",
            "recommended_service",
            "summary",
            "raw_transcript",
            "unclear_fields",
        ],
    },
}


def transcribe(image_bytes: bytes, mime_type: str, additional_notes: str = "") -> dict:
    """Returns the structured fields. `additional_notes` (typed context from the
    Supabase row, not on the notes page) is provided to the model as authoritative
    extra context to merge into the relevant fields."""
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    if mime_type == "application/pdf":
        source_block = {"type": "input_file", "filename": "demo_notes.pdf", "file_data": data_url}
    else:
        source_block = {"type": "input_image", "image_url": data_url}

    extra = (
        f"\n\nAdditional context provided separately by the sales team (authoritative — "
        f"merge it into the relevant fields even if it is not on the page):\n{additional_notes.strip()}"
        if additional_notes and additional_notes.strip()
        else ""
    )

    content = [
        source_block,
        {
            "type": "input_text",
            "text": (
                "Transcribe this sales demo-call notes page and extract the fields defined "
                "in extract_demo_notes. If handwriting is illegible or a field isn't present, "
                "leave it as an empty string and list its name in unclear_fields rather than "
                "guessing." + extra
            ),
        },
    ]

    return llm_client.call_tool(content, EXTRACTION_TOOL)


def missing_required_fields(fields: dict) -> list[str]:
    missing = [name for name in config.REQUIRED_OCR_FIELDS if not fields.get(name)]
    missing += [name for name in fields.get("unclear_fields", []) if name in config.REQUIRED_OCR_FIELDS]
    seen = set()
    result = []
    for name in missing:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result
