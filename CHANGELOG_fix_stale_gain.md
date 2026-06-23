# Lazy_MkPFS Studio — Fix stale Active Build Gain on new build

Scope: **`active_build.py` only.** No model changes, no gain calculation changes,
no behaviour/default changes, no pipeline/forbidden files touched.

## Bug

When a new build started right after a completed one, the Active Build **Gain**
tile kept showing the *previous* build's gain (e.g. "63.6%") all through the new
build's Scan / Create-exFAT phases — before any compression had happened and no
real gain existed.

## Root cause

`set_steps()` is the `job_start` handler. It rebound the job, built the phase
dots and showed build controls, but **did not reset the stat tiles**. Gain is only
refreshed at completion (`on_done` / `_render_summary`), so without a reset it
retained the last build's value. (The job model was correct — `BuildJob.gain`
defaults to 0.0 and is only set at `job_done` — so this was purely a UI tile-reset
bug.)

## Fix (file: `lazy_studio/pages/active_build.py`, `set_steps`)

Reset the live display to its initial state at `job_start`:

- Stat tiles: Speed `—`, Progress `0%`, ETA `—`, Elapsed `0s`, Phase `—`,
  **Gain `—`**.
- Top percent label `0%`, top phase label `Waiting…`.
- Progress bar: stop any indeterminate animation first (`_set_indeterminate(False)`),
  then set the bar to `0` (determinate).

Ordering: the indeterminate animation is stopped before resetting the bar; the
upcoming scan `phase` event re-enables indeterminate via
`set_phase()`→`update_progress()` if the new build is in a scan-like phase — so the
scan UX still works. `update_progress`, `on_done`, `_render_summary` and the gain
calculation are unchanged.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb test (the exact reported scenario):
  - Build 1 completes → Gain tile "63.6%".
  - Build 2 starts → **Gain resets to "—"** (and Speed/Progress/ETA/Elapsed/Phase,
    top labels, and bar all reset; bar determinate at 0).
  - During Scan → Gain stays "—"; bar correctly re-enters indeterminate.
  - During Create exFAT 52% → Gain still "—"; real speed/percent flow normally.
  - Build 2 completes → Gain shows real "72.0%".
- Regression: app builds; all 7 pages render; Active Build idle path works.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff` vs the previously delivered archive: only `active_build.py` changed, and
  the diff is exactly the reset block added to `set_steps` (no other method touched).
