"""The heart of v2: inspect a deck at run-level detail, edit client-specific
text *in place* (preserving every surrounding run's style), and render slide
thumbnails so a human/Claude can visually verify design fidelity.

Why in-place edits (scoped `replaceAllText`) instead of v1's delete+insert:
a delete+insert wipes all run/paragraph styling in the shape, so v1 had to
re-apply a single captured style — which cannot reproduce per-word highlights
(only "objectives" highlighted in "Learning Objectives", only "INVESTMENT" in
"YOUR INVESTMENT"). `replaceAllText` swaps only the matched phrase and leaves
every other run untouched, so those highlights survive automatically. We simply
never touch the static styled headers, and only swap the client-specific body
text/figures/dates.
"""

import io

import requests


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

def _color_repr(color: dict) -> str:
    """Compact human-readable colour, e.g. 'rgb(1.0,0.8,0.0)' or 'theme:ACCENT1'."""
    if not color:
        return ""
    opaque = color.get("opaqueColor", color)
    if "themeColor" in opaque:
        return f"theme:{opaque['themeColor']}"
    rgb = opaque.get("rgbColor")
    if rgb is not None:
        r = round(rgb.get("red", 0.0), 3)
        g = round(rgb.get("green", 0.0), 3)
        b = round(rgb.get("blue", 0.0), 3)
        return f"rgb({r},{g},{b})"
    return ""


def _runs_for_shape(element: dict) -> list[dict]:
    """Flattens a shape's textElements into a list of run summaries, so highlight
    boundaries (a colour/style change mid-line) are visible."""
    runs = []
    text_elements = element.get("shape", {}).get("text", {}).get("textElements", [])
    for te in text_elements:
        run = te.get("textRun")
        if not run or "content" not in run:
            continue
        content = run["content"]
        if not content.strip("\n"):
            # Keep newline-only runs out of the summary; they add noise.
            continue
        style = run.get("style", {})
        fg = _color_repr(style.get("foregroundColor", {}))
        bg = _color_repr(style.get("backgroundColor", {}))
        size = style.get("fontSize", {}).get("magnitude")
        runs.append({
            "text": content.replace("\n", "\\n"),
            "foreground": fg,
            "background": bg,
            "bold": bool(style.get("bold", False)),
            "italic": bool(style.get("italic", False)),
            "font_size": size,
            "font_family": style.get("fontFamily", ""),
        })
    return runs


def _shape_full_text(element: dict) -> str:
    text_elements = element.get("shape", {}).get("text", {}).get("textElements", [])
    return "".join(
        te.get("textRun", {}).get("content", "") for te in text_elements
    ).strip()


def _has_bullets(element: dict) -> bool:
    text_elements = element.get("shape", {}).get("text", {}).get("textElements", [])
    return any("bullet" in te.get("paragraphMarker", {}) for te in text_elements)


def _elements_of(page: dict) -> list[dict]:
    """Shared element summariser for a slide or a layout page."""
    elements = []
    for element in page.get("pageElements", []):
        object_id = element["objectId"]
        if "shape" in element:
            full_text = _shape_full_text(element)
            if not full_text:
                continue
            elements.append({
                "object_id": object_id,
                "type": "shape",
                "full_text": full_text,
                "has_bullets": _has_bullets(element),
                "runs": _runs_for_shape(element),
            })
        elif "image" in element:
            elements.append({
                "object_id": object_id,
                "type": "image",
                "title": element.get("title", ""),
                "description": element.get("description", ""),
            })
    return elements


def dump(slides, presentation_id: str) -> dict:
    """Returns a JSON-serializable, run-level view of every slide AND every layout
    the slides use:
    {presentation_id, title,
     slides:  [{index, slide_id, layout_id, elements: [...]}],
     layouts: [{layout_id, display_name, used_by_slides: [idx...], elements: [...]}]}.

    `index` is 1-based (matches the slide numbers in the v2 spec). Each element is
    a shape (with per-run text/colour/bold/size so highlights are visible) or an
    image (id + alt text). Layouts are included because this template keeps the
    cover slide's client tagline, date, and logos on a *custom layout*, not on
    slide 1 — so tailoring the cover means editing the layout's text (scope an
    edit to `layout_id`). This is what lets a caller build precise, unambiguous
    find/replace edits and see which words are highlighted."""
    presentation = slides.presentations().get(presentationId=presentation_id).execute()
    out = {
        "presentation_id": presentation_id,
        "title": presentation.get("title", ""),
        "slides": [],
        "layouts": [],
    }

    layouts_by_id = {lay["objectId"]: lay for lay in presentation.get("layouts", [])}
    layout_usage: dict[str, list[int]] = {}

    for index, slide in enumerate(presentation.get("slides", []), start=1):
        layout_id = slide.get("slideProperties", {}).get("layoutObjectId")
        if layout_id:
            layout_usage.setdefault(layout_id, []).append(index)
        out["slides"].append({
            "index": index,
            "slide_id": slide["objectId"],
            "layout_id": layout_id,
            "elements": _elements_of(slide),
        })

    # Only surface layouts that (a) a slide actually uses and (b) carry text —
    # those are the ones with client-specific cover content worth editing.
    for layout_id, used_by in layout_usage.items():
        layout = layouts_by_id.get(layout_id)
        if not layout:
            continue
        elements = _elements_of(layout)
        if not any(e["type"] == "shape" for e in elements):
            continue
        out["layouts"].append({
            "layout_id": layout_id,
            "display_name": layout.get("layoutProperties", {}).get("displayName", ""),
            "used_by_slides": used_by,
            "elements": elements,
        })

    return out


# ---------------------------------------------------------------------------
# In-place editing
# ---------------------------------------------------------------------------

def _slide_id_by_index(slides, presentation_id: str) -> dict:
    presentation = slides.presentations().get(
        presentationId=presentation_id, fields="slides.objectId"
    ).execute()
    return {
        i: s["objectId"]
        for i, s in enumerate(presentation.get("slides", []), start=1)
    }


def apply_edits(slides, presentation_id: str, edits: list[dict]) -> dict:
    """Applies scoped find/replace edits in one batchUpdate.

    Each edit: {"find": str, "replace": str, and one of "slide_id" or
    "slide_index", plus optional "match_case" (default True)}. Every edit is
    scoped with `pageObjectIds=[slide_id]` so a short phrase (a date, a figure)
    can only ever match on its own slide. Returns
    {requests: N, replacements: [{find, occurrences}...], total_occurrences}."""
    index_map = None
    requests = []
    for edit in edits:
        find = edit["find"]
        replace = edit.get("replace", "")
        slide_id = edit.get("slide_id")
        if not slide_id:
            if index_map is None:
                index_map = _slide_id_by_index(slides, presentation_id)
            slide_id = index_map[int(edit["slide_index"])]
        requests.append({
            "replaceAllText": {
                "containsText": {
                    "text": find,
                    "matchCase": edit.get("match_case", True),
                },
                "replaceText": replace,
                "pageObjectIds": [slide_id],
            }
        })

    if not requests:
        return {"requests": 0, "replacements": [], "total_occurrences": 0}

    response = slides.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()

    replacements = []
    total = 0
    for edit, reply in zip(edits, response.get("replies", [])):
        occ = reply.get("replaceAllText", {}).get("occurrencesChanged", 0)
        total += occ
        replacements.append({"find": edit["find"], "occurrences": occ})
    return {"requests": len(requests), "replacements": replacements, "total_occurrences": total}


# ---------------------------------------------------------------------------
# Thumbnails (visual verification)
# ---------------------------------------------------------------------------

def thumbnails(slides, presentation_id: str, slide_indexes: list[int], out_dir: str) -> dict:
    """Saves a PNG thumbnail of each requested slide (1-based index) to out_dir.
    Returns {saved: [{index, slide_id, path}...]}. The contentUrl from
    getThumbnail is short-lived, so we fetch it immediately."""
    import os

    os.makedirs(out_dir, exist_ok=True)
    index_map = _slide_id_by_index(slides, presentation_id)
    saved = []
    for index in slide_indexes:
        slide_id = index_map[int(index)]
        thumb = slides.presentations().pages().getThumbnail(
            presentationId=presentation_id,
            pageObjectId=slide_id,
            thumbnailProperties_thumbnailSize="LARGE",
        ).execute()
        content_url = thumb["contentUrl"]
        resp = requests.get(content_url, timeout=60)
        resp.raise_for_status()
        path = os.path.join(out_dir, f"slide_{int(index):02d}.png")
        with io.open(path, "wb") as f:
            f.write(resp.content)
        saved.append({"index": int(index), "slide_id": slide_id, "path": path})
    return {"saved": saved}
