# Lazy_MkPFS Studio — Fix Build Wizard freeze on Step 4 → Step 5 (Review)

Scope: **`build_wizard.py` only.** No pipeline/frozen files touched. `preflight.py`
untouched. Same outputs, same preflight rules, same Add-to-Queue / Start-Now logic.

## Bug

Clicking **Next** from "File Naming" to "Review & Start" froze the app
("Not Responding"), worst with multiple/large dump folders.

## Root cause

`_step_summary` (Review render) called `PF.estimate_job(job)` **synchronously on the
UI thread, once per source, inside the widget-building loop**. For folder sources
`estimate_job` invokes `lazy_mkpfs.create_exfat.calculate_exfat_size`, which does a
full recursive `os.walk` over every file in the dump. With 4 sources (incl. a
148.8 GB and a 74.3 GB game) that was four full directory walks back-to-back before
a single Review widget painted, blocking the Tk event loop.

It compounded: when the (already threaded) preflight finished, `_poll_preflight`
called `_render()`, which re-ran `_step_summary` → re-walked every folder on the UI
thread again, and Back→Next did the same.

## Fix (file: `lazy_studio/pages/build_wizard.py`)

1. **Removed the synchronous `PF.estimate_job` call from `_step_summary`.** The
   Review step now renders immediately with no filesystem work.
2. **Added `_estimate_for(idx)`** — returns the per-source `JobEstimate` from the
   *already-computed* threaded preflight result (`self._pf_result.estimates`),
   paired by source index, **only when `self._pf_hash == self._preflight_hash()`**
   (current inputs). It performs no filesystem work and is bounded by a length
   check so a stale/partial result can never mis-index onto the wrong source.
3. **Placeholders while pending:** when no valid estimate exists yet, the Review
   rows show `Est. temporary space: Checking space…` and
   `Est. final size: Checking space…`. Everything else (filename, stages,
   destination, verify, delete-warning, totals) renders instantly.
4. **Source size stays cached:** the "Source" fact and the "Total source size"
   line use the staged source's `s.size`, captured off-thread at add time
   (`_StagedSource.detect` → `M.dir_size`). Dumps are never re-walked on Review.
5. **Preflight stays threaded:** `_maybe_run_preflight` is unchanged (background
   thread + hash cache) and remains the single source of estimates via
   `PF.check_queue`.
6. **Stale-guarded re-render:** `_poll_preflight` now re-renders only when the
   completed result matches the current step *and* the current inputs hash. If the
   user changed sources while a preflight was in flight, the stale result is
   ignored (rejected by hash in `_estimate_for`), the Review keeps showing
   "Checking space…", and `_step_summary`'s tail starts a fresh preflight for the
   current inputs (its own guards prevent a duplicate run).

`PF.estimate_job` is no longer called anywhere in the wizard. `PF.check_queue`
(threaded) and the `PF.PASS/WARN/BLOCK` gating are unchanged.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- **Behavioral test with 4 real dump folders + a thread-aware spy on
  `calculate_exfat_size`:**
  - Review render returned in ~0.29 s with **0 `calculate_exfat_size` calls on the
    main thread** (all 4 walks ran on a background `work` thread).
  - Estimates showed pending ("Checking space…") immediately, then filled in after
    the threaded preflight completed (status reported correctly).
  - **Back → Next: 0 UI-thread walks, 0 new walks total** (cached) — no freeze.
  - Changing the source set rejected the stale estimate (hash mismatch), then a
    fresh preflight produced estimates matching the new source count.
  - **Start Now disabled under BLOCK** — gating logic unchanged.
- 1-source path renders through all 5 steps (incl. a size-0 folder) without crash.
- Regression: app builds; all 7 pages render; wizard steps 1–5 render.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK, incl.
  `create_exfat.py`, which is only read by preflight — never modified).
- `diff -rq` vs the previously delivered archive: **only `build_wizard.py` changed.**
