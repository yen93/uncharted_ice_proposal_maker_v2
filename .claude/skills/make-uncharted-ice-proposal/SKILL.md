---
name: make-uncharted-ice-proposal
description: Build a tailored Uncharted Ice sales proposal deck from a client's demo-call notes. Given a Google Drive link to the notes (photo/scan/PDF/Doc), it transcribes them, creates a client folder in the master Proposals drive, transfers the notes in, copies the master proposal template, tailors the client-specific slides (cover, 1, 2, 3, 4, 6, 7, 12) in place preserving the deck's exact design/highlights, deletes the program-framework slide, keeps only the bonus slides actually offered in the notes, and swaps the client logo. Use when the user asks to make/build/generate an Uncharted Ice proposal, run the v2 proposal maker, or turn demo notes into a proposal deck.
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

## Slide map (1-indexed on the freshly-copied 13-slide deck) — memorize this

- **Tailor (retext in place, keep the design):** 1, 2, 3, 4, 6, 7, 12
  (+ the cover **layout** tagline/date).
- **Delete (structural — do these LAST, after all text edits, by objectId):**
  - **5** ("THE PROGRAM FRAMEWORK", objectId `g3f73b73fc1d_0_8`) — ALWAYS delete.
  - **Bonus slides 9 & 10** — conditional (see the bonus step): slide 9 = Debrief
    Call (`g2f9b7407bc0_0_290`), slide 10 = Executive X (`g2f9b7407bc0_0_431`).
    Delete a bonus slide only if that bonus is NOT ticked in the notes. If NEITHER
    bonus is ticked, also delete slide 8 (the bonus intro, `g2f9b7407bc0_0_148`).
- **Leave untouched:** 8 (bonus intro, if kept), 11 (client feedback/testimonials),
  13 (closing "THANK YOU"). The client logo on all kept slides is still swapped (step 8).

Why delete LAST and by objectId: object IDs are stable and don't shift when other
slides are deleted, so you can tailor by the 13-slide indices above, then remove
slides in any order without re-numbering.

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

6. **Tailor slides 1, 2, 3, 4, 6, 7, 12 — in place.**
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
     move logos, text boxes, or anything's placement.
   - **Learning objectives are the spine (Liv's feedback).** Tailor slide 3's
     objectives to the client's themes FIRST, then make slides 2, 4 and 7 clearly
     relate to those same objectives:
     - **Slide 2 (bio, "NAVIGATING UNCHARTED WATERS"):** make it a bit more
       detailed and explicitly connect Cas's story to the client's learning
       objectives (e.g. name the objective areas the session builds).
     - **Slide 4 ("PROGRAM COMPONENTS"):** this is now tailored, not verbatim. Its
       component blurbs (Facilitation / Adventure Simulation / Skill-Development)
       must reflect the client's objectives, and you MUST remove the old-client
       reference — the template says "tailored to SWIM's leadership and growth
       objectives"; swap "SWIM's leadership and growth objectives" for the client's.
     - **Slide 7 ("HOW THE UNCHARTED ICE WORKS"):** relate the outcomes back to the
       client's learning objectives.
     - **Slide 6 ("WHAT IS UNCHARTED ICE?") — tailor the OPENING too (Liv's
       feedback):** this slide's expedition backstory has three paragraphs — (1) the
       expedition backdrop, (2) the expedition facts, (3) a closing question to the
       client. Don't tailor only the closing question: rework paragraphs 1 AND 2 so
       the expedition reads as a mirror of THIS client's situation and objectives
       (e.g. tie the resilience, decision-making and teamwork the journey demanded to
       what the client's team faces), while keeping the factual expedition details
       (the route, distances, temperatures, the Guinness world-first) accurate.
   - **Slide 12 (YOUR INVESTMENT) — duration (Liv's feedback):** the DELIVERY
     section must state the session **duration** and keep it **highlighted** like
     the template. The template highlights the run "3-DAY IN-PERSON"; replace that
     highlighted run IN FULL with the client's duration (e.g. "FULL-DAY IN-PERSON",
     "3-DAY IN-PERSON", "6HR IN-PERSON") so the highlight is preserved. Also update
     the investment figures.
   - **Keep replacements close to the original length** so text doesn't overflow
     its box. Trim detail rather than exceeding it.
   - Read the `occurrences` in the result — a `0` means your `find` didn't match
     (fix the exact text and retry that edit).

7. **Bonus slides (conditional) + delete structural slides — do this LAST, after
   all text edits.**
   The bonus-value slides are 8 (intro), 9 (Debrief Call, $995) and 10 (Executive
   X invite, $2,995). From the notes' **ADD BONUS VALUE** checklist, keep only the
   bonuses that are ticked:
   - If **both** ticked → keep 8, 9, 10 as-is (intro already says "2 … gifts valued
     at more than $3,995").
   - If **only one** ticked → delete the other bonus slide, and edit slide 8's intro
     from "2 value-packed bonus gifts valued at more than $3,995" to
     "1 value-packed bonus gift valued at more than $995" (Debrief only) or
     "$2,995" (Executive X only).
   - If **neither** ticked → delete slides 8, 9 and 10.
   Then delete the structural slides (all deletions by **objectId** via
   `python v2_tools.py delete-slide <deck_id> <object_id>`):
   - ALWAYS: `delete-slide <deck_id> g3f73b73fc1d_0_8` (THE PROGRAM FRAMEWORK).
   - Un-ticked Debrief Call → `delete-slide <deck_id> g2f9b7407bc0_0_290`.
   - Un-ticked Executive X → `delete-slide <deck_id> g2f9b7407bc0_0_431`.
   - Neither bonus ticked → also `delete-slide <deck_id> g2f9b7407bc0_0_148` (intro).
   Leave slide 11 (client testimonials) and slide 13 (closing) untouched. The client
   logo on the kept slides is still swapped in step 8.

8. **Swap the client logo.**
   The template ships with the previous client's (SWIM) logo on the cover and in
   the footer of several slides. Replace it with the new client's logo:
   - Find a **public, direct** image URL for the client's logo — a link ending in
     `.png`/`.jpg` that Google's servers can fetch without login (companieslogo.com,
     brandfetch, a press kit, Wikimedia, etc.; use WebSearch/WebFetch to get the
     direct file URL, not a page URL). **Prefer a white/mono "dark background"
     version** — the cover and footers sit on a dark panel.
   - `python v2_tools.py replace-logo <new_deck_id> "<image_url>"` — this swaps all
     of the client-logo image slots (`config.CLIENT_LOGO_IMAGE_IDS`) at once and
     reports which were `replaced`/`missing`. The "My Adventure Group" logo is left
     untouched. If it errors, the URL probably isn't publicly fetchable — pick
     another and retry (text edits are unaffected).
   - If you genuinely can't find a good logo, skip and flag it in the QA note for
     hand-placement rather than inserting a poor one.

9. **Verify visually.**
   Slide indices shift once you delete slides in step 7, so **re-dump first**
   (`python v2_tools.py dump-slides <new_deck_id>`) to get the FINAL slide numbers,
   then render the tailored slides:
   `python v2_tools.py thumbnails <new_deck_id> "<final indices>" "<scratchpad>/thumbs"`.
   `Read` each PNG. Check: the framework slide is gone; only the ticked bonus
   slides remain (and slide 8's count/value matches); wording is client-tailored
   and slides 2/4/7 relate to the objectives; slide 12's DELIVERY shows the
   highlighted duration; highlights, bullet colours, fonts and placement are
   otherwise unchanged; the **client logo is the right one and looks right on the
   dark panel**; nothing overflows. Fix issues with `apply-edits`/`replace-logo`/
   `delete-slide` and re-render.

10. **Report.** Give the user:
    - the folder link and the deck edit link,
    - a one-line summary of what you tailored per slide, and whether the logo was
      swapped (and from what source),
    - a short **QA note** of anything a human should double-check before sending
      (e.g. a figure you inferred, a possible overflow, the swapped logo — confirm
      it's correct and on-brand).

11. **Email the proposal link to the reviewer.**
    `python v2_tools.py email-proposal "<Client Name>" "<deck_url>" "<folder_url>"`
    This emails the deck + folder links to the reviewer, **Liv**
    (`config.NOTIFY_EMAIL` = liv@myadventuregroup.com.au), from the account owner's
    Gmail. The reviewer is always the recipient — do not send it to the owner
    instead. Confirm the result's `message_id` and tell the user it was sent to Liv.

## Notes / gotchas

- **Never delete+reinsert a shape's text to edit it** — that wipes its styling.
  Always go through `apply-edits` (scoped `replaceAllText`), which preserves the
  surrounding runs. This is the whole reason v2 exists (v1's rewriter couldn't
  keep per-word highlights).
- **The client logo IS swapped** (step 8, `replace-logo`) across the cover and
  every footer, via fixed object IDs in `config.CLIENT_LOGO_IMAGE_IDS` (stable
  because Drive copies preserve object IDs). It still needs a human eye —
  auto-found logos can be the wrong variant/colour — so verify it in step 9 and
  flag it in the QA note.
- Safe to re-run: `make-folder` reuses an existing client folder. Re-running
  `apply-edits` after the wording is already changed will just report `0`
  occurrences for phrases that no longer exist — harmless. `replace-logo` is
  idempotent too (just replaces the same slots again).
