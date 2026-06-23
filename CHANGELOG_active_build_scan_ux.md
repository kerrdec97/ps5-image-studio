# Lazy_MkPFS Studio — Active Build scan UX (indeterminate state)

Scope: **`active_build.py` only.** No pipeline/forbidden files touched. No worker,
no job_runner, no create_exfat. No fabricated counters — UI motion only.

## Problem

During Phase 1 (Scan) and the pre-copy part of Create exFAT, the child process
runs `calculate_exfat_size`'s `os.walk` and emits **no progress telemetry**. The
Active Build bar therefore sat at a dead **0%** with no speed/ETA while Elapsed
climbed (e.g. 3m 27s @ 0%), which reads as "frozen / hung" even though work is
ongoing. (Real file/byte counters can't be shown without editing the forbidden
pipeline files, per the prior audit.)

## Change (file: `lazy_studio/pages/active_build.py`)

Detect the no-telemetry scan state and animate an **indeterminate** progress bar
instead of showing a dead 0%:

- `_is_scan_like_phase(phase)` — phases whose work emits no progress (Scan,
  Create exFAT).
- `_wants_indeterminate(job)` — True only when the phase is scan-like AND
  `progress <= 0` AND no `speed` has been emitted AND the job isn't terminal. The
  moment a real progress line lands (pct>0 or a speed), this returns False.
- `_set_indeterminate(on)` — idempotently toggles
  `CTkProgressBar.configure(mode=…)` + `start()/stop()`. Falls back silently to a
  static bar if the CTk build lacks indeterminate mode (the "Scanning…" label and
  live Elapsed still convey motion).

Wiring:
- `update_progress()` branches: in the indeterminate state it animates the bar,
  shows a prominent **"Scanning source — large titles can take several minutes to
  analyse"** message, sets the percent to **"—"** (not 0%) and the Progress tile to
  "scanning…"; otherwise it behaves exactly as before (determinate bar, real
  percent/speed/ETA).
- `set_phase()` also routes through `update_progress()` so entering a scan-like
  phase (which arrives as a `phase` event, not a `progress` event) starts the
  animation.
- Animation is explicitly stopped and the bar returned to determinate mode in
  `on_done()`, `_render_summary()` and `_render_idle()`.

Real determinate progress (e.g. Create exFAT copy at 52% / 423 MB/s, Compress,
Verify, Move) is unchanged — those emit telemetry and were never the problem.

Elapsed already ticks independently via the app pump, so the timer keeps moving
during scan with no change needed there.

Note: the **file count in the completion summary** (report item #2) was already
present in `on_done()`/`_render_summary()` from a prior slice ("… · 166,726 files
· <output path>") and is confirmed working by the test below.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb lifecycle test:
  - Scan @ 0% / no speed → bar `indeterminate`, percent "—", "Scanning source…"
    message with "Phase 1 of 5".
  - Create exFAT pre-copy @ 0% / no speed → still indeterminate.
  - Real copy @ 52% / 423 MB/s → flips to `determinate`, percent "52%", bar 0.52.
  - Compress @ 30% → stays determinate.
  - Done → animation stopped, determinate 100%, "166,726 files" in summary.
  - New scan on a new job re-enters indeterminate; idle stops the animation.
- Regression: app builds; all 7 pages render; Active Build idle path works.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff` vs the previously delivered archive: only `active_build.py` changed.
