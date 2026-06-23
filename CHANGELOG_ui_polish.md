# Lazy_MkPFS Studio — UI Polish Pass

Scope: **UI only.** No build-pipeline files touched. No output logic changed. No
defaults changed. Page keys unchanged. AddJobPage retained (still reachable from
Queue → "✚ Add").

## Files changed (7, all under `lazy_studio/`)

- `lazy_studio/app.py`
- `lazy_studio/pages/build_wizard.py`
- `lazy_studio/pages/history.py`
- `lazy_studio/pages/settings.py`
- `lazy_studio/pages/edit_image.py`
- `lazy_studio/pages/queue.py`
- `lazy_studio/pages/dashboard.py`

## Files explicitly NOT touched (verified byte-identical to input)

- `lazy_studio/worker.py`
- `lazy_studio/job_runner.py`
- `lazy_mkpfs/create_exfat.py`
- `lazy_mkpfs/pack_folder.py`
- `lazy_mkpfs/pack_file.py`
- `lazy_mkpfs/pack_verify.py`

The entire `lazy_mkpfs/` package is unchanged (frozen pipeline).

## Changes

### 1. Removed redundant titlebar "← Home" button (`app.py`)
Every workspace page already carries a prominent top-left "🏠 Home" button. The
small duplicate in the titlebar was removed: its creation in `_build_titlebar`
and the `pack`/`pack_forget` toggles in `enter_mode()`/`go_home()` are gone. The
in-page Home buttons are untouched. (`home_btn` attribute no longer exists.)

### 2. Build Wizard vertical density (`build_wizard.py`)
Stepper style and Next/Back unchanged. Tightened spacing only:
- Shared card header pad `(20,12)→(16,10)`; inter-card gap `(0,8)→(0,10)` kept
  modest and uniform.
- Step 1 mode box internal padding reduced (more compact mode selector).
- Step 2 empty "Sources" panel shortened (top/bottom `22→14`).
- Step 3 format cards: header/size-hint/compression-line paddings trimmed.
- Step 4 preview cards: field row spacing and trailing spacer trimmed.

### 3. Stronger delete-source warning (`build_wizard.py`)
Behaviour unchanged (still opt-in, default OFF, deletion handled by the pipeline).
When enabled, the warning is now a **filled amber row** on both the File Naming
step and the Review & Start plan, with explicit wording:
"Source will be deleted only after a successful verify/move … cannot be undone."
When disabled it stays as quiet helper text / a neutral "No" fact.

### 4. History empty-state fix (`history.py`)
Fixed the bug where an empty/filtered history showed a tall card with a table
header strip and a lone centered label. Now renders a proper empty-state card:
- **"No history yet"** when history is genuinely empty.
- **"No results for this filter"** when a filter hides every row.
CTAs: **New Build** always; **Clear filter** when a filter is active (resets to
"All"). The table header is skipped entirely in the empty case. Filters and
Clear History are unchanged.

### 5. Settings density (`settings.py`)
All "Recommended:" and "Current default:" help text preserved; no defaults or
behaviour changed (`_set` untouched). Tightened card header pad, per-row bottom
gaps and separator gaps, grouped the rec/default lines closer to their row, and
trimmed the hand-rolled Compression block spacing.

### 6. Edit exFAT Image empty-state (`edit_image.py`)
Added an idle empty-state card shown when no image is selected:
"Open an exFAT image to browse it read-only", a note that the original image is
never modified, and an "Open .exfat Image" button. Mount / read-only behaviour
is unchanged.

### 7. Queue card polish (`queue.py`)
- Long game titles now wrap cleanly (`wraplength`) instead of pushing the status
  pill/actions off the card.
- Action buttons normalized to a consistent width (88): Stop / Move Up / Remove.
- Live-progress references untouched.

### 8. Overview polish (`dashboard.py`)
- Last Build card corner radius brought in line with the other cards (10→8) so it
  leads by accent border, not by size; trailing button-row padding trimmed.
- Existing card alignment (uniform grid groups), Build Health, Next Job, Defaults,
  Storage bars and Recent Outputs all retained unchanged.

## Verification performed

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0.
- `ast.parse` on all 7 edited files → OK.
- Headless import of all edited modules + app shell → OK.
- Full GUI smoke test under Xvfb: app builds; all 8 page keys render; wizard
  steps 1–5 render; delete-source ON paths render; both history empty-state
  variants render; `go_home()` works; `app.home_btn` confirmed absent.
- Forbidden-file SHA-256 checksums verified identical to input (all 6 OK).
- `diff -rq` vs input confirms exactly the 7 intended files changed.
