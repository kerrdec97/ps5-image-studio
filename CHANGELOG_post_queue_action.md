# Lazy_MkPFS Studio — Post-queue action (Part B)

Scope: 3 files — `models.py`, `app.py`, `pages/settings.py`. No pipeline/forbidden
files touched. Default "Do nothing" — existing users unaffected. No build pipeline
behaviour changed.

## Feature

Optionally put the PC to sleep or shut it down after the **whole queue finishes
successfully**, with a 60-second cancellable countdown.

## Definition of "successful queue completion" (strict all-clean)

The action fires only when the queue fully drains AND the batch summary has:
`done > 0` AND `error == 0` AND `cancelled == 0`. Any errored or cancelled job in
the batch blocks the action.

## Changes

**`models.py`** — `Settings.post_queue_action: str = "nothing"`
(`"nothing" | "sleep" | "shutdown"`). Default satisfies "Do nothing";
backward-compatible via `Settings.load`.

**`app.py`**
- The three terminal handlers (done/error/cancelled) now capture
  `batch_maybe_drain()`'s return and call `_on_queue_drained()` when it fires
  (it returns True exactly once, when the queue empties).
- `_on_queue_drained()`: evaluates the strict all-clean rule; if met and the action
  is sleep/shutdown, starts the countdown. Fully guarded (try/except) — never
  disrupts anything.
- `_start_post_queue_countdown()`: a `CTkToplevel` with a live 60s counter and a
  **Cancel** button. For **shutdown** it also schedules the OS's own cancellable
  timer (`shutdown /s /t 60`) so there's a safety net even if the app exits;
  **sleep** has no cancellable native timer, so it only fires at countdown expiry.
- `_pq_tick()`: 1-second countdown via `self.after`; at expiry fires sleep (shutdown
  was already scheduled with the OS timer) and closes the dialog.
- `_cancel_post_queue_countdown()`: Cancel button, window-close, AND a new
  `job_start` all call this; it aborts a pending OS shutdown (`shutdown /a`) and
  destroys the dialog.
- `_run_shutdown_command()` / `_run_sleep_command()`: Windows commands
  (`shutdown /s /t N`, `rundll32.exe powrprof.dll,SetSuspendState 0,1,0`), guarded
  to a logged no-op on non-Windows. Launched with `CREATE_NO_WINDOW` where available.
- `job_start` calls `_cancel_post_queue_countdown()` so starting a new build cancels
  a pending countdown.

**`pages/settings.py`** — new "When the Queue Finishes" card with a
"Post-queue action" SegBar (Do nothing / Sleep / Shutdown) → `_set("post_queue_action")`.
(Credits & Support card moved from grid row 8 to 9 to make room.)

## Verification

- `compileall` + `ast` on all 3 files → clean.
- Xvfb tests:
  - Command builders: shutdown → `["shutdown","/s","/t","60"]` (cancellable),
    sleep → `rundll32.exe ... SetSuspendState`; **linux builds nothing** (no-op).
  - Cancel issues `shutdown /a` and clears the dialog.
  - Strict gate: `nothing`→no action; clean `(done=3,err=0,cancel=0)`→fires;
    `error`/`cancel`/`zero-done`→blocked; `sleep` clean→fires.
  - Countdown window creates correctly; `_pq_tick` counts down and fires sleep at
    expiry; shutdown is not pre-fired (OS timer scheduled, in-app counts down).
  - `job_start` calls `_cancel_post_queue_countdown` (auto-cancel on new build).
  - Settings card renders; `_set` works; round-trip persists; fresh default is
    `"nothing"`. All 7 pages render.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff -rq` vs prior archive: only the 3 expected files changed.

Note on testing: a couple of window-path assertions in an earlier test run failed
only because stubbing `subprocess.Popen` module-wide broke Tk internals under the
headless Xvfb harness — not a code defect. The window-creation path was verified
working with the real `subprocess` in place, and all command/gate/cancel logic was
verified directly.
