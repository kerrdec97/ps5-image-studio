# Lazy_MkPFS Studio — Compact Build Wizard Review (Step 5)

Scope: **`build_wizard.py` only** (the body of `_step_summary`). No pipeline/forbidden
files touched. No wizard flow, source/order logic, output naming, preflight logic,
or Add-to-Queue / Start-Now behaviour changed.

## Problem

Step 5 rendered one tall card per source with repeated label blocks (Output
filename / Full output path / Output type / Source / Est. temp / Est. final /
Archive destination / Verify), plus a delete-source warning repeated for every
source. For 4–10 sources this was very long and read like a repeated form.

## Change (file: `lazy_studio/pages/build_wizard.py`, `_step_summary`)

Replaced the per-source cards with a compact table:

- A `BG4` column header (Game · PPSA · Output filename · Format · Size), mirroring
  the History page's table style.
- **One row per source**: Game (title, ellipsised) · PPSA · Output filename
  (`job.out_name`) · Format (FFPFSC/exFAT) · Source size (`human_size(s.size)`),
  plus a small **destination-folder** detail line (`→ <final_dir>`).
- The full output path is intentionally **not** repeated per row — it's
  reconstructable from the destination folder + the filename shown in the row,
  which keeps the review clean.
- **One consolidated facts line** below the table:
  `Total source size · Verify after build: On/Off · Delete source: Yes/No`
  (instead of repeating Verify/Delete per source).
- **One** amber delete-source warning section, shown once when delete is enabled
  (was previously repeated per source). Wording preserved in substance.
- The **Space preflight panel is unchanged** and still carries the per-volume
  space story (required/free, Staging/Archive), so the per-row Est. temp/final and
  Archive-destination facts were removed as redundant.

Result: Step 5 drops from ~7–9 rows/source to **1 row + 1 detail line/source** —
roughly a 70% height reduction for 4+ sources — and reads like a final queue
summary rather than a repeated form.

## Safety precondition (verified before and after)

`_step_summary` does **not** call `PF.estimate_job` or any filesystem-walking
primitive (`dir_size`, `os.walk`, `calculate_exfat_size`, `.stat`, `disk_usage`).
It renders from cached source data only — `s.title`/`s.ppsa`/`s.size` (captured
off-thread at add time) and `job.out_name`/`job.final_dir()` (pure string/`Path`
construction, no FS access, confirmed in models.py). Space estimates remain
**async-only**: the threaded preflight (`_maybe_run_preflight`/`_poll_preflight`)
is untouched and still hash-guarded; `_render_preflight()` reads the cached result.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb test with a thread-aware spy on `calculate_exfat_size`:
  - **0 filesystem walks during the Review render** (the safety guarantee).
  - All 4 games render with title/PPSA/output-filename; ASTRO BOT filename shown
    as `PPSA21567 ASTRO BOT (01.018.000).ffpfsc`.
  - **4 destination-FOLDER lines** (`→ …`), none ending in the filename (folder,
    not full path).
  - **One** consolidated facts line (`Total source size … · Verify … · Delete …`).
  - Delete OFF → 0 warnings; Delete ON with 4 sources → **exactly 1** warning.
  - Single-source renders cleanly; preflight result still arrives async.
- Regression: app builds; all 7 pages render; wizard steps 1–5 render; Back/Next
  around Review works.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff` vs the previously delivered archive: only `build_wizard.py` changed.

Note: `_stages_for` and `_estimate_for` are no longer called from `_step_summary`
(stages moved out of the compact rows; estimates are surfaced only in the preflight
panel). They were left defined — self-contained and harmless — rather than removed,
to keep this slice minimal.
