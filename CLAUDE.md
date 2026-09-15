# CLAUDE.md

Guidance for a future Claude Code session working in this repo.

## What this is

`uncharted_ice_proposal_maker_v2` builds a tailored Uncharted Ice sales proposal
deck from a client's demo-call notes. Unlike v1 (`../uncharted_ice_proposal_maker`,
a fully-automated Gmail/Form-triggered pipeline), **v2 is an interactive Claude
Code routine**: you run the `/make-uncharted-ice-proposal` skill, hand it a Google
Drive link to the notes, and Claude drives the steps — transcribe → make client
folder → transfer notes → copy the master template → tailor the client slides →
verify → report.

The authoritative routine is `.claude/skills/make-uncharted-ice-proposal/SKILL.md`.

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
- The finished, non-client slides (**4, 8-11, 13**) are left **completely
  untouched**.
- The client slides (**1, 2-3, 5-7, 12**) are edited **in place** via scoped
  `replaceAllText` (see `src/slides_service.py`), which swaps only the matched
  phrase and leaves every other run's styling intact. The static styled headers
  are never touched, so their highlights/bullet colours survive automatically.

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
python v2_tools.py thumbnails    <presentation_link> <1,2,3,...> <out_dir>
```

## Config & credentials

- Non-secret config in `project_vars.txt`: `proj_drive_link` (the master
  Proposals folder every client folder is created under) and `template_link`
  (the master deck). `config.py` extracts the IDs and holds the slide map
  (`TAILOR_SLIDES` / `VERBATIM_SLIDES`) and scopes (`drive`, `presentations`).
- `.env` holds the Google OAuth creds, **reused from v1** (same Google account,
  julienne@myadventuregroup.com.au). v1's refresh token already carries the
  drive+presentations scopes v2 needs, so no separate consent flow is normally
  required. Only run `python oauth_setup.py` if the token is missing/revoked.
- `.env` is gitignored; `.env.example` is tracked. Real secrets go only in `.env`.

## Key conventions / gotchas

- **Folder is named the bare client name** (no year suffix) — this differs from
  v1's "`Client Year`" convention, per the v2 spec.
- **`apply-edits` is scoped per slide** (`pageObjectIds`). Still prefer long,
  unambiguous `find` phrases: a bare date/number can match twice on one slide.
  A `0`-occurrence reply means the `find` text didn't match — fix the exact
  string (copy it from `dump-slides`) and retry.
- **The cover (slide 1) content lives on a custom layout, not the slide.** The
  big "UNCHARTED ICE" title, the client tagline, the date, and the logos are all
  on "Custom Layout 4". `dump-slides` surfaces used layouts in a `layouts`
  section, and `apply-edits` can scope to a `layout_id`, so the skill retexts the
  cover **tagline + date on the layout**. The client **logo** (an image on the
  layout) is still **not auto-swapped** — placed by hand; the skill flags this in
  its QA note. Don't change the "UNCHARTED ICE" program title.
- `dump-slides` reports per-**run** styling on purpose — that run-level view is
  how you tell a highlighted word from its neighbours before writing edits. Keep
  it.
