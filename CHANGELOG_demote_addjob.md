# Lazy_MkPFS Studio — Demote legacy AddJobPage

Scope: **UI routing only, one file.** No build-pipeline files touched. No output
logic changed. No defaults changed. No page keys removed or renamed.

## File changed (1)

- `lazy_studio/pages/queue.py`

## File explicitly NOT changed

- `lazy_studio/pages/add_job.py` — AddJobPage is **retained**, still imported and
  registered in `app.py` under the stable key `"addjob"`. It is now a hidden
  fallback: registered and fully functional if routed to directly, but no longer
  linked from anywhere in the UI.

## Change

Queue's "✚ Add" button previously opened the legacy AddJobPage:

    ghost_btn(tb, "✚  Add", lambda: self.app.show_page("addjob"), ...)

It now opens the modern Build Wizard, matching every other "New Build" entry
point (Home, Overview, Active Build, History):

    ghost_btn(tb, "✚  Add", lambda: self.app.enter_mode("build"), ...)

`enter_mode("build")` is the canonical modern entry used elsewhere; when called
from inside the shell (as here) its pack-guards are no-ops, so it is behaviourally
equivalent to `show_page("build")` but consistent with the rest of the app.

## Audit basis

- Queue line 30 was the **only** navigation entry point into the `"addjob"` page
  in the entire codebase (grep for `show_page("addjob")` / `enter_mode("addjob")`
  returns nothing after this change). Home does not link to it.
- The `app.add_job` / `app.add_job_from_path` methods (used by the Build Wizard,
  History and Overview) are the job-submission API — distinct from the page — and
  are unchanged.
- AddJobPage submits via that same `app.add_job` API, so demoting it loses no
  capability the Wizard lacks.

## Verification performed

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0.
- `ast.parse` on `queue.py` → OK.
- Xvfb GUI smoke test invoking the **actual** Queue "Add" button command:
  Queue → Add lands on the Build Wizard (`_current == "build"`); shell body stays
  mapped (not stuck on Home); AddJobPage still registered and still renders when
  routed to directly.
- Forbidden-file SHA-256 checksums verified identical to input (all 6 OK).
- `diff -rq` vs the previously delivered archive confirms exactly one file changed
  in this slice: `queue.py`.
