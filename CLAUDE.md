# CLAUDE.md

Guidance for a future Claude Code session working in this repo.

## What this is

`uncharted_ice_proposal_maker_v2` builds a tailored Uncharted Ice sales proposal
deck from a client's demo-call notes. **Everything is Claude-driven — there is NO
OpenAI/LLM-API dependency anywhere.** Claude transcribes the notes, writes the
highlight-safe edits, and reads the ADD BONUS VALUE checkboxes with its own vision.
There are two ways to run it, sharing the same helpers and producing the same output:

1. **Interactive skill** — `/make-uncharted-ice-proposal`
   (`.claude/skills/make-uncharted-ice-proposal/SKILL.md`). You hand Claude a Drive
   link to the notes; Claude drives the steps. This is the **authoritative definition
   of the process** (slide map, highlight rules, delete/bonus rules).
2. **Automated cloud routine** — `uncharted-ice-proposal-maker-v2`
   (`trig_016A8ahwJy4x7DKjxFhTmGh5` at claude.ai/code/routines, hourly at :45 UTC,
   Default env). The routine's own Claude agent reads that SKILL.md, drains the
   Supabase queue `proposal_demo_notes_email_logs` (`python v2_tools.py queue-list`),
   does the same steps per row, and marks each `queue-done`. Update its prompt/secrets
   via the RemoteTrigger tool. `/run-uncharted-ice-pipeline` is the manual, on-demand
   version of the same drain.

The flow: transcribe → client folder → transfer notes → copy the master template →
tailor the client slides in place → delete the program-framework slide → keep only
the offered bonus slides → swap the client logo → email the link to Liv → mark the row
done. The automated runs can't visually self-verify, so they flag anything uncertain
as `needs_review`.

## Why v2 exists (the core design decision)

v1's slide rewriter does a delete-all + insert and then re-applies a single
captured style per shape. That **cannot reproduce per-word highlights** — only
"objectives" highlighted in "Learning Objectives", only "INVESTMENT" in "YOUR
INVESTMENT", only "PROGRAM" in "PROGRAM COMPONENTS" — so v1 output needed heavy
hand-correction against the sales specialist's deck (see v1's
`150926 - modifications.txt`).

v2 changes the strategy:
- The master template (`config.V2_TEMPLATE_ID`) is already the
  sales-specialist-quality deck.
- The client slides (**1, 2, 3, 4, 6, 7, 12** + the cover layout) are edited **in
  place** via scoped `replaceAllText` (see `src/slides_service.py`), which swaps only
  the matched phrase and leaves every other run's styling intact. The static styled
  headers are never touched, so their highlights/bullet colours survive automatically.
- Structural changes are applied LAST by objectId: slide 5 (framework) is always
  deleted; the bonus slides (8-10) are kept only when ticked in the notes. See the
  SKILL.md slide map for the authoritative list + object IDs.

**Never** switch v2 back to a delete+insert rewrite to "tailor" a slide — that
reintroduces exactly the formatting loss v2 was built to avoid.

## Running it

```
pip install -r requirements.txt
```
Then use `/make-uncharted-ice-proposal` inside Claude Code. The skill shells out
to `v2_tools.py` for every Google operation (each prints JSON):

```
python v2_tools.py fetch-notes   <drive_link> <out_path>
python v2_tools.py make-folder   "<Client>"
python v2_tools.py move-file     <file_link> <folder_id>
python v2_tools.py copy-template <folder_id> "<deck name>"
python v2_tools.py save-text     <folder_id> "<filename>" <local_text>
python v2_tools.py dump-slides   <presentation_link>
python v2_tools.py apply-edits   <presentation_link> <edits_json>
python v2_tools.py replace-logo  <presentation_link> <public_image_url>
python v2_tools.py delete-slide  <presentation_link> <slide_index_or_object_id>
python v2_tools.py thumbnails    <presentation_link> <1,2,3,...> <out_dir>
python v2_tools.py email-proposal "<client>" "<deck_url>" "<folder_url>"
python v2_tools.py queue-list                       # unprocessed Supabase rows
python v2_tools.py queue-done    <row_id> <status> <proposal_link|-> <error|->
```

For the **automated queue** (the cloud routine, or `/run-uncharted-ice-pipeline`
manually): `queue-list` reads `proposal_demo_notes_email_logs` (project
`aivitcomiywiysrfwqxt`) where `is_processed is null or false`, newest first. Each row
provides **`demo_notes_link`** (Drive link to the notes) and **`additional_notes`**
(extra typed context). `queue-done` sets `is_processed=true`, `status`
(`success`/`needs_review`/`error`), `proposal_link` — so a bad row is never retried.

**Highlight rule (critical, in SKILL.md):** a `find` must never *span* a highlight
boundary, but it MAY replace a highlighted run in full (e.g. highlighted "3-DAY
IN-PERSON" → "FULL-DAY", keeping the highlight). Don't loosen it to "never touch
highlighted runs" (leaves stale highlighted text) nor allow boundary-spanning finds
(collapses the highlight).

## Config & credentials

- Non-secret config in `project_vars.txt`: `proj_drive_link` (the master
  Proposals folder every client folder is created under) and `template_link`
  (the master deck). `config.py` extracts the IDs and holds the slide map
  (`TAILOR_SLIDES` / `VERBATIM_SLIDES`) and scopes (`drive`, `presentations`).
- `.env` holds the Google OAuth creds, **reused from v1** (same Google account,
  julienne@myadventuregroup.com.au). v1's refresh token already carries the
  drive+presentations+gmail.send scopes v2 needs, so no separate consent flow is
  normally required. Only run `python oauth_setup.py` if the token is missing/revoked.
- The **automated queue** additionally needs `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`
  in `.env` (reused from v1) — for `queue-list`/`queue-done`. No OpenAI/LLM key is
  used anywhere; Claude does the transcription + tailoring itself.
- `.env` is gitignored; `.env.example` is tracked. Real secrets go only in `.env`.

## Key conventions / gotchas

- **Folder is named the bare client name** (no year suffix) — this differs from
  v1's "`Client Year`" convention, per the v2 spec.
- **`apply-edits` is scoped per slide** (`pageObjectIds`). Still prefer long,
  unambiguous `find` phrases: a bare date/number can match twice on one slide.
  A `0`-occurrence reply means the `find` text didn't match — fix the exact
  string (copy it from `dump-slides`) and retry.
- **The cover (slide 1) content lives on a custom layout, not the slide.** The
  big "UNCHARTED ICE" title, the client tagline, and the date are on "Custom
  Layout 4". `dump-slides` surfaces used layouts in a `layouts` section, and
  `apply-edits` can scope to a `layout_id`, so the skill retexts the cover
  **tagline + date on the layout**. Don't change the "UNCHARTED ICE" program
  title. (The cover SWIM logo is a slide-1 image, not a layout image — see below.)
- **The client logo IS swapped** (`replace-logo`). The client-logo images (cover +
  the right side of each footer lockup) have fixed object IDs listed in
  `config.CLIENT_LOGO_IMAGE_IDS`; these are stable because **Drive copies preserve
  object IDs**, so the swap targets them deterministically across every generated
  deck. `replace-logo` issues `replaceImage` (CENTER_INSIDE) with a public image
  URL Google fetches server-side — so the URL must be public/direct, and the
  result (variant/colour on the dark panel) always needs a human check. The "My
  Adventure Group" logo (left of each footer) is deliberately excluded. If the
  master template is ever rebuilt, re-derive these IDs via image geometry (client
  logo sits at x≈1.98" in footers; MAG at x≈0.88").
- **A "proposal ready" email** goes to the reviewer, **Liv** (`config.NOTIFY_EMAIL`
  = liv@myadventuregroup.com.au) through `src/gmail_service.py` — never to the
  account owner. The `NOTIFY_EMAIL` env override exists only to repoint the reviewer
  if that role changes; leave it unset in production. This needs the `gmail.send`
  scope, which is in `config.GOOGLE_SCOPES` and already granted on the reused v1
  refresh token — no new consent required.
- `dump-slides` reports per-**run** styling on purpose — that run-level view is
  how you tell a highlighted word from its neighbours before writing edits. Keep
  it.
