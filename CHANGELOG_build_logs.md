# Lazy_MkPFS Studio — Save build logs (Part A)

Scope: 5 files — `models.py`, `app.py`, `pages/settings.py`, `pages/history.py`,
`pages/dashboard.py`. No pipeline/forbidden files touched. Default OFF — existing
users are unaffected. No build pipeline behaviour changed.

## Feature

Optionally save a `.txt` build log (metadata header + full log) for every build,
to a user-chosen folder. History "Log" and Overview "View Log" open the saved file
when one exists, else fall back to the existing in-app popup.

## Changes

**`models.py`** (additive, backward-compatible)
- `Settings`: `save_logs: bool = False`, `logs_path: str = ""`. `Settings.load`
  ignores unknown keys and defaults missing ones, so old `settings.json` loads with
  logging OFF.
- `HistoryEntry`: `log_path: str = ""`. `load_history` defaults it for old rows;
  `save_history` (asdict) serialises it.
- New `sanitize_filename(name, max_len=60)` helper: strips Windows-illegal chars
  (`\ / : * ? " < > |`) and control chars, collapses whitespace to `_`, caps length.

**`app.py`** — `_record_history` (single completion point for done/error/cancelled)
- New `_write_build_log(...)`: when `save_logs` is on, resolves the folder
  (`logs_path` or `<archive>/logs`), `mkdir(exist_ok=True)`, writes a sanitized file
  `PPSA_TITLE_YYYY-MM-DD_HHMM_<outcome>.txt` with a metadata header (title, PPSA,
  output path, format, source size, stored size, gain, elapsed, result, timestamp)
  followed by the **full** `job.log`, and returns the path. Collisions (same
  title/minute) get a seconds/counter suffix. Entirely wrapped in try/except —
  a write failure is logged and swallowed, never affecting the build or history.
- Sets `entry.log_path` and `job.log_path` so both History and Overview's
  `last_finished` can open it.

**`pages/settings.py`** — new "Build Logs" card (after Naming)
- "Save build logs" toggle → `_set("save_logs", v)` (default Off).
- "Log folder" path field → `_set("logs_path", v)` (blank => `<archive>/logs`).
- Uses the existing `_row`/`_path_field`/`_set` pattern; `_set` unchanged.

**`pages/history.py`**
- New `_open_file(path)` helper: opens the FILE itself (not its parent folder)
  cross-platform; returns False if the file is missing so callers can fall back.
- `_show_log(h)`: opens `h.log_path` if it exists, else the existing popup.

**`pages/dashboard.py`**
- `info` dict carries `log_path` (from `last_finished` or `history[0]`).
- `_show_log(title, log, log_path)`: opens the saved file if present (reusing
  history's `_open_file`), else the existing popup.

## Verification

- `compileall` + `ast` on all 5 files → clean.
- Xvfb tests:
  - `sanitize_filename` strips illegal chars / handles empty.
  - Settings round-trip: `save_logs`/`logs_path` persist and reload.
  - Disabled → no file written, `log_path == ""`.
  - Enabled → file `PPSA21567_ASTRO_BOT_..._done.txt` written with correct header
    and the **full** log (all 250 lines, not the 200-line history cap);
    `entry.log_path` and `job.log_path` set.
  - error and cancelled also write (`_error.txt` / `_cancelled.txt`).
  - Same title within one minute → distinct files (collision avoided).
  - `log_path` persisted in `history.json`.
  - `_open_file`: missing → False, real file → True.
  - History `_show_log` with a missing `log_path` → popup fallback, no crash.
  - Settings page renders the Build Logs card; `_set` works for the new keys.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff -rq` vs prior archive: only the 5 expected files changed.
