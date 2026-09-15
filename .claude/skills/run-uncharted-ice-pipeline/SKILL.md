---
name: run-uncharted-ice-pipeline
description: Run the AUTOMATED Uncharted Ice proposal pipeline once (python main.py) — drains the Supabase queue (proposal_demo_notes_email_logs, unprocessed rows), and for each row builds the tailored proposal deck from its demo_notes_link + additional_notes, swaps the client logo, emails Liv the link, and marks the row processed. Use when the user asks to run/trigger/kick off the automated proposal pipeline, or process the queued demo-note rows now. (For a single interactive build from a pasted Drive link, use make-uncharted-ice-proposal instead.)
---

# Run Uncharted Ice pipeline (automated)

Runs the same code path the user's API trigger runs. This is the automated, no-human
counterpart to `make-uncharted-ice-proposal` — it reads work from Supabase instead of a
pasted link, and uses OpenAI (not you) to transcribe the notes and write the slide edits.

## Steps

1. Confirm `.env` exists with the Google, OpenAI, and Supabase values (see `.env.example`).
   If missing, stop and tell the user — don't fabricate credentials.
2. Run from the project root:
   ```
   python main.py
   ```
3. Read the `pipeline` logger output. It reports how many unprocessed rows were found and, per
   row, the proposal link + status (`success` / `needs_review`) or an `error` with the reason.
4. Summarise for the user: rows found/processed, each proposal link and status, and any
   `needs_review`/`error` reasons. Don't paste the raw log.

## Notes

- Safe to re-run: rows are marked `is_processed=true` when done, so they drop out of the queue;
  a failed row is marked `error` (not retried forever).
- Each finished proposal emails its links to `config.NOTIFY_EMAIL` (liv@myadventuregroup.com.au).
  To avoid emailing Liv during a test, run with `NOTIFY_EMAIL=<your address>` set in the env.
- `ModuleNotFoundError` → `pip install -r requirements.txt` and retry.
