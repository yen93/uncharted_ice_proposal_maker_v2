"""Generate highlight-safe slide edits with OpenAI — the automated stand-in for
what Claude does by hand in the interactive skill's step 6.

It feeds the model the transcription + additional_notes + the tailorable shapes
(slides 1,2,3,5,6,7,12 and the cover layout), each with its full text and the list
of highlighted run texts to leave alone, and asks for exact contiguous find/replace
swaps. The result is mapped straight into slides_service.apply_edits() format, so
the actual edit still goes through scoped `replaceAllText` — per-word highlights are
preserved by construction, exactly as in the skill.
"""

import json

import config
from src import llm_client

TAILOR_TOOL = {
    "name": "tailor_proposal_text",
    "description": "Exact find/replace text swaps that tailor the Uncharted Ice proposal deck to a new client, preserving all formatting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The slide index as a string ('1','2','3','5','6','7','12') or 'layout' for the cover layout (tagline/date).",
                        },
                        "find": {
                            "type": "string",
                            "description": "Exact contiguous substring copied verbatim from that shape's text — no newlines, and never overlapping a highlighted run.",
                        },
                        "replace": {
                            "type": "string",
                            "description": "The client-tailored replacement, kept close to the original length.",
                        },
                    },
                    "required": ["location", "find", "replace"],
                },
            }
        },
        "required": ["edits"],
    },
}

_RULES = (
    "You are tailoring a sales proposal deck (originally written for a previous client) to a "
    "NEW client, by emitting exact find/replace text swaps. STRICT RULES:\n"
    "1. Every `find` MUST be copied verbatim from a shape's `full_text` below, and be a single "
    "contiguous span with NO newline characters.\n"
    "2. A shape may have HIGHLIGHTED runs (listed per shape as `highlighted_runs`). Your `find` "
    "must NEVER span a highlight boundary — it may lie entirely inside non-highlighted text, OR "
    "equal one highlighted run's exact text in full, but never start inside a highlighted run and "
    "end outside it (or vice-versa). You MAY replace a highlighted run in full when it is "
    "client-specific: set `find` to that run's exact text and the replacement keeps the highlight "
    "(e.g. a highlighted '3-DAY IN-PERSON' -> 'FULL-DAY', or '3 DAY' -> 'FULL DAY'). Do NOT edit "
    "pure header/title shapes at all (e.g. 'LEARNING OBJECTIVES', 'YOUR INVESTMENT', "
    "'THE PROGRAM FRAMEWORK', 'WHAT IS UNCHARTED ICE?', 'NAVIGATING UNCHARTED WATERS', "
    "'HOW THE UNCHARTED ICE WORKS').\n"
    "3. Keep `replace` within ~15% of the `find` length so text doesn't overflow its box.\n"
    "4. Only change CLIENT-SPECIFIC content: the client's name, the program/session framing "
    "(e.g. a 3-day retreat vs a full-day/6hr session), dates, audience description, the learning "
    "objectives/themes bullets, program day-structure, and investment figures. Leave generic "
    "narrative, the expedition story, and boilerplate unchanged.\n"
    "5. Never change the program title 'UNCHARTED ICE'. For location 'layout', tailor only the "
    "tagline sentence and the date.\n"
    "6. Use the demo notes AND the additional notes as the source of truth for the new wording. "
    "If you are unsure a phrase is client-specific, leave it alone.\n"
    "Return only the edits."
)


def _tailorable_shapes(dump: dict) -> tuple[list[dict], str]:
    """Builds the compact shape list for the model and returns
    (shapes, cover_layout_id)."""
    tailor = set(config.TAILOR_SLIDES)
    shapes = []
    for slide in dump.get("slides", []):
        if slide["index"] not in tailor:
            continue
        for el in slide.get("elements", []):
            if el["type"] != "shape":
                continue
            shapes.append({
                "location": str(slide["index"]),
                "full_text": el["full_text"],
                "highlighted_runs": [
                    r["text"].replace("\\n", " ").strip()
                    for r in el.get("runs", [])
                    if r.get("background")
                ],
            })

    cover_layout_id = ""
    for lay in dump.get("layouts", []):
        if 1 in lay.get("used_by_slides", []):
            cover_layout_id = lay["layout_id"]
            for el in lay.get("elements", []):
                if el["type"] != "shape":
                    continue
                # Skip the "UNCHARTED ICE" title outright.
                if el["full_text"].strip().upper() == "UNCHARTED ICE":
                    continue
                shapes.append({
                    "location": "layout",
                    "full_text": el["full_text"],
                    "highlighted_runs": [],
                })
            break
    return shapes, cover_layout_id


def build_edits(fields: dict, additional_notes: str, dump: dict) -> list[dict]:
    """Returns a list of edits in slides_service.apply_edits() format:
    [{slide_index|slide_id, find, replace}]. 'layout' locations are mapped to the
    cover layout's objectId so the edit is scoped there."""
    shapes, cover_layout_id = _tailorable_shapes(dump)

    content = [{
        "type": "input_text",
        "text": (
            _RULES
            + "\n\nDemo notes (transcribed):\n" + json.dumps(fields, indent=2, ensure_ascii=False)
            + "\n\nAdditional notes:\n" + (additional_notes.strip() or "(none)")
            + "\n\nTailorable shapes:\n" + json.dumps(shapes, indent=2, ensure_ascii=False)
        ),
    }]

    raw_edits = llm_client.call_tool(content, TAILOR_TOOL)["edits"]

    edits = []
    for e in raw_edits:
        find = e.get("find", "")
        if not find or "\n" in find:
            continue
        loc = str(e.get("location", "")).strip()
        edit = {"find": find, "replace": e.get("replace", "")}
        if loc == "layout":
            if not cover_layout_id:
                continue
            edit["slide_id"] = cover_layout_id
        else:
            try:
                edit["slide_index"] = int(loc)
            except (TypeError, ValueError):
                continue
        edits.append(edit)
    return edits
