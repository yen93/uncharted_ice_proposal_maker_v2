---
name: run-uncharted-ice-pipeline
description: Manually drain the Uncharted Ice proposal queue right now (Claude-driven, no OpenAI) — the same work the hourly cloud routine does, run on demand. Reads the Supabase queue (proposal_demo_notes_email_logs, unprocessed rows) and, for each row, builds the tailored proposal deck from its demo_notes_link + additional_notes, deletes/keeps slides per Liv's rules, swaps the client logo, emails Liv the link, and marks the row processed. Use when the user asks to run/trigger/kick off the proposal pipeline, or process the queued demo-note rows now. (For a single build from a pasted Drive link, use make-uncharted-ice-proposal instead.)
---

# Run Uncharted Ice pipeline (manual queue drain)

This is the manual, on-demand counterpart to the hourly cloud routine
(`uncharted-ice-proposal-maker-v2` at claude.ai/code/routines). **You (Claude) do the whole
job yourself** — transcribe the notes, write the highlight-safe edits, and read the ADD BONUS
VALUE checkboxes with your own vision. There is **no OpenAI** anywhere in this project.

## Steps

1. Confirm `.env` exists with the Google + Supabase values (see `.env.example`). If missing,
   stop and tell the user — don't fabricate credentials.
2. From the project root, run:
   ```
   python v2_tools.py queue-list
   ```
   It prints the unprocessed rows `[{id, demo_notes_link, additional_notes}]`. If empty, report
   "no rows to process" and stop — that's a healthy outcome.
3. **For each row**, follow the full `make-uncharted-ice-proposal` process (read that skill's
   `SKILL.md` — it's authoritative), but source the notes from the row's `demo_notes_link` and
   fold in `additional_notes`:
   - `fetch-notes` → Read + transcribe yourself → derive the client name (if the notes have no
     readable client name, `python v2_tools.py queue-done <id> error - "could not read client_org"`
     and skip).
   - `make-folder` → `move-file` the notes in + `save-text` the transcription.
   - `copy-template` → `dump-slides` → tailor slides 1,2,3,4,6,7,12 + cover layout
     (highlight-safe; tie slides 2/4/7 to the slide-3 objectives; slide-12 duration highlighted).
   - Bonus + structural (LAST): from the ADD BONUS VALUE ticks, keep only offered bonuses
     (adjust the intro; `delete-slide` the un-ticked bonus slides) and always `delete-slide` the
     PROGRAM FRAMEWORK slide.
   - `replace-logo` (find a public client-logo URL) → `email-proposal` (emails Liv) →
     `queue-done <id> <status> <deck_url> -`.
4. Summarise for the user: per row — client, status (`success`/`needs_review`), and the deck
   link; or "no rows to process".

## Notes

- Safe to re-run: rows are marked processed when done and drop out of the queue; a failed row is
  marked `error` (not retried forever).
- Emails always go to the reviewer, **Liv** (`config.NOTIFY_EMAIL`) — don't redirect to the owner.
  To dry-run without emailing Liv, set `NOTIFY_EMAIL=<your address>` in the env.
- `ModuleNotFoundError` → `pip install -r requirements.txt` and retry.
