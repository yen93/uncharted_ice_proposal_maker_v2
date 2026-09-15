---
name: make-uncharted-ice-proposal
description: Build a tailored Uncharted Ice sales proposal deck from a client's demo-call notes. Given a Google Drive link to the notes (photo/scan/PDF/Doc), it transcribes them, creates a client folder in the master Proposals drive, transfers the notes in, copies the master proposal template, and tailors the client-specific slides (1, 2-3, 5-7, 12) in place — preserving the deck's exact design/highlights — while leaving the finished slides (4, 8-11, 13) untouched. Use when the user asks to make/build/generate an Uncharted Ice proposal, run the v2 proposal maker, or turn demo notes into a proposal deck.
---

# Make Uncharted Ice proposal (v2)

Interactive routine. You (Claude) drive each step, doing the wording/tailoring
yourself and shelling out to `v2_tools.py` for every Google operation. The
guiding principle: **edit text in place, never rebuild slides.** The template is
already the sales-specialist-quality deck; your job is to swap only the
client-specific wording on the client slides and leave everything else exact.

## Before you start

- Ask the user for the **Google Drive link to the demo notes** if they didn't
  provide one. Optionally ask for the **client/company name** (you can also
  derive it from the notes and confirm).
- Confirm `.env` exists in the project root. If missing, stop and tell the user
  to run `python oauth_setup.py` (v2 normally reuses the shared refresh token, so
  this should already be set). Don't fabricate credentials.
- Run all `python v2_tools.py ...` commands from the project root. Each prints a
  JSON result — read it before the next step.
- Use the session scratchpad for temp files (the downloaded notes, thumbnails,
  `edits.json`).

## Slide map (1-indexed) — memorize this

- **Tailor (retext in place, keep the design):** 1, 2, 3, 5, 6, 7, 12
- **Leave completely untouched:** 4, 8, 9, 10, 11, 13

## Steps

1. **Transcribe the notes.**
   `python v2_tools.py fetch-notes "<drive_link>" "<scratchpad>/notes<ext>"`
   Then `Read` the downloaded file and transcribe it to text. Pull out
   everything client-specific: company/organisation name, contact, event date,
   audience, location, program/objective wording, investment figures, and any
   design/delivery details. Decide the **client name** (this names the folder);
   confirm with the user if it's ambiguous. Keep the transcription as your single
   source of truth for wording. Save it to `<scratchpad>/transcription.txt`.

2. **Create the client folder.**
   `python v2_tools.py make-folder "<Client Name>"` → note `folder_id` / `view_url`.
   (Reuses the folder if it already exists.)

3. **Transfer the notes + save the transcription.**
   - `python v2_tools.py move-file "<drive_link>" <folder_id>` (moves the original
     notes file into the folder; falls back to a copy if it can't be moved).
   - `python v2_tools.py save-text <folder_id> "<Client> - Demo Notes.txt" "<scratchpad>/transcription.txt"`.

4. **Copy the master template into the folder.**
   `python v2_tools.py copy-template <folder_id> "<Client> - Uncharted Ice Proposal"`
   → note the new `file_id` (the working deck) and `view_url`.

5. **Inspect the new deck.**
   `python v2_tools.py dump-slides <new_deck_id>` → this gives you every slide's
   shapes and **per-run** text with colours/bold/size (so you can see exactly
   which words are highlighted), plus a **`layouts`** section. Read it carefully
   and, for each tailored slide, list the client-specific phrases to swap vs. the
   static styled headers to leave alone.
   **Cover slide (important):** slide 1's big "UNCHARTED ICE" title, the
   client **tagline**, the **date**, and the **logos** are NOT on the slide —
   they live on its **custom layout** (see the `layouts` entry whose
   `used_by_slides` includes 1). To retext the cover tagline/date you edit that
   layout, scoping the edit to its `layout_id` (see step 6). The client **logo**
   on the layout is an image — it is not swapped automatically; flag it for
   hand-placement.

6. **Tailor slides 1, 2-3, 5-7, 12 — in place.**
   Build an `edits.json` (a list of edits) and run
   `python v2_tools.py apply-edits <new_deck_id> "<scratchpad>/edits.json"`.
   Each edit is:
   ```json
   { "slide_index": 3, "find": "<exact old phrase>", "replace": "<new phrase>" }
   ```
   (You may use `"slide_id"` from the dump instead of `slide_index`; add
   `"match_case": false` only when needed.)
   **Cover layout edits:** to retext slide 1's tagline/date, set `"slide_id"` to
   the cover's `layout_id` (from the dump's `layouts` section) — `apply-edits`
   scopes to any page id, layouts included. E.g. swap the old tagline phrase and
   the old date (`"MAY 2027"` → the client's month/year). Do **not** touch the
   "UNCHARTED ICE" title.
   Rules:
   - **Find the longest, unambiguous old phrase** you can — the exact text as it
     appears in the dump. Every edit is scoped to its slide, but short strings
     (a bare date/number) can still hit twice on one slide; prefer a distinctive
     surrounding phrase.
   - **Only touch client-specific wording.** Never include a static styled header
     (e.g. "YOUR INVESTMENT", "Learning Objectives", "PROGRAM COMPONENTS") in a
     `find` — leaving those runs untouched is exactly what preserves their
     per-word highlights and bullet colours.
   - **Slide 1:** tailor the subtitle line on the slide (e.g. the
     "3 DAY … RETREAT WITH …" shape) and, on the cover **layout**, the client
     tagline and the date. Keep the "UNCHARTED ICE" program title as-is. Do NOT
     move logos, text boxes, or anything's placement; the client logo is
     hand-placed (see QA note).
   - **Keep replacements close to the original length** so text doesn't overflow
     its box. Trim detail rather than exceeding it.
   - Read the `occurrences` in the result — a `0` means your `find` didn't match
     (fix the exact text and retry that edit).

7. **Leave slides 4, 8-11, 13 alone.** No edits.

8. **Verify visually.**
   `python v2_tools.py thumbnails <new_deck_id> "1,2,3,5,6,7,12" "<scratchpad>/thumbs"`
   `Read` each PNG. Check: wording is correct and client-tailored; highlights,
   bullet colours, fonts, and placement are unchanged from the template; nothing
   overflows or overlaps. If anything is off, fix it with a follow-up
   `apply-edits` and re-render that slide. (Optionally also render 4/8-11/13 once
   to confirm they're identical to the template.)

9. **Report.** Give the user:
   - the folder link and the deck edit link,
   - a one-line summary of what you tailored per slide,
   - a short **QA note** of anything a human should double-check before sending
     (e.g. a figure you inferred, a possible overflow, the client logo on slide 1
     which is not auto-swapped — add it by hand if needed).

## Notes / gotchas

- **Never delete+reinsert a shape's text to edit it** — that wipes its styling.
  Always go through `apply-edits` (scoped `replaceAllText`), which preserves the
  surrounding runs. This is the whole reason v2 exists (v1's rewriter couldn't
  keep per-word highlights).
- The **client logo on slide 1 is not swapped automatically** (it lives on a
  custom layout). Flag it in the QA note so it's placed by hand, matching the
  template's logo placement.
- Safe to re-run: `make-folder` reuses an existing client folder. Re-running
  `apply-edits` after the wording is already changed will just report `0`
  occurrences for phrases that no longer exist — harmless.
