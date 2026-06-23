# Lazy_MkPFS Studio — Remove legacy AddJobPage

Scope: **Remove the legacy AddJobPage entirely.** No build-pipeline files touched.
No output logic changed. No defaults changed. The job-submission API is untouched.
Remaining page keys are unchanged.

## Files changed (4) + 1 deleted

Modified:
- `lazy_studio/app.py` — removed the `AddJobPage` import and the `"addjob"` entry
  from the page registry.
- `lazy_studio/pages/build_wizard.py` — docstring updated (AddJobPage removed,
  no longer "stays registered as a fallback"). Comment only.
- `lazy_studio/pages/queue.py` — comment updated (AddJobPage removed entirely).
  Comment only; the button already routed to `enter_mode("build")`.
- `STUDIO_README.md` — removed the `add_job.py` line from the file tree.

Deleted:
- `lazy_studio/pages/add_job.py` — the legacy page. It was imported only by
  `app.py` and defined only `SRC_OPTS` (used nowhere else) and `AddJobPage`.

## Explicitly NOT changed

- `app.add_job` and `app.add_job_from_path` (defined in `app.py`) — the
  job-submission API. AddJobPage merely *called* `app.add_job`; it did not define
  the API. The Build Wizard, History rebuild and Overview rebuild all use this API
  directly and are unaffected.
- `worker.py`, `job_runner.py`, `create_exfat.py`, `pack_folder.py`,
  `pack_file.py`, `pack_verify.py` — verified byte-identical.

## Audit basis

- No UI navigated to `"addjob"`: `grep show_page("addjob") / enter_mode("addjob")`
  returned nothing (Queue's Add had already been repointed to the Build Wizard in
  the prior slice).
- `pages/add_job.py` was imported only by `app.py:16`; nothing imported `SRC_OPTS`
  or `AddJobPage` from it; it imported only shared modules (theme/models/widgets/
  base). The PyInstaller `.spec` does not name it.
- Removing it therefore affects no other page or AppState.

## Remaining page keys (stable)

`dashboard, queue, active, history, settings, build, edit`
(`"addjob"` removed; nothing renamed; default target `_current="dashboard"`
unaffected.)

## Verification performed

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0.
- `ast.parse` on all edited `.py` files → OK.
- Xvfb GUI smoke test:
  - `"addjob"` not in `app.pages`; key set is exactly the 7 above.
  - `show_page("addjob")` is a safe no-op (logs "page 'addjob' unavailable",
    stays on the current page, no crash).
  - Home → Build Wizard works.
  - Queue → Add → Build Wizard works (invoked the real button command).
  - History `_rebuild` calls `add_job_from_path` with the correct args.
  - Overview `_rebuild` calls `add_job_from_path` with the correct args.
- Forbidden-file SHA-256 checksums verified identical to input (all 6 OK).
- `diff -rq` vs the previously delivered archive confirms exactly: `app.py`,
  `build_wizard.py`, `queue.py`, `STUDIO_README.md` modified; `add_job.py`
  removed; nothing else.
