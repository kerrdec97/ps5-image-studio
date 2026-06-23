# Lazy_MkPFS Studio — Fix History crash (missing models import)

Scope: **one file, one line.** No pipeline/forbidden files touched. No History
logic, filters, stats, row rendering, or persistence changed.

## Bug

After a real FFPFSC build that saved space (e.g. ASTRO BOT, `148.8 GB → 41.6 GB`),
opening **History** left the page blank — even though Overview showed the same
entries.

## Root cause

`lazy_studio/pages/history.py` referenced `M.human_size(...)` at module scope
(line 160, in `_build_stats`) but the file never imported `models as M`. When a
history row had a parseable `"X GB → Y GB"` sizes string with a positive saving,
`_history_stats` set `saved_bytes` non-None, so `_build_stats` reached the
`M.human_size(...)` line and raised:

    NameError: name 'M' is not defined

`_build_stats` runs at the top of `refresh()` (before any rows render), so the
exception aborted the whole refresh → blank card *and* blank stats strip. It was
intermittent because the crash line only executes when there's a compressing row
with a positive saving; empty history and exFAT-only rows (no `→`) skipped it,
which is why earlier empty-state testing passed.

(Overview reads the same `state.history` but never calls `human_size` on aggregate
saved-bytes, so it rendered fine — confirming the record was written and the bug
was in History's render path, not data or filters.)

## Fix

`lazy_studio/pages/history.py` — added one import alongside the existing
`from ..` imports:

    from .. import models as M

Nothing else changed. (Note: `_clear()` already had a function-local
`from .. import models as M`, which is why Clear History didn't crash before; that
local import is now redundant but was left untouched to keep this a minimal,
logic-free one-line fix.)

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb runtime test with a compressing FFPFSC record + a mixed exFAT record:
  - History renders rows and the stats strip (subtitle "2 builds · avg 72.0% gain").
  - **Space Saved tile** computes correctly (107.2 GB from `148.8 GB → 41.6 GB`).
  - **Clear History** runs without crashing; empty-state re-renders.
  - **Overview** still reads history and renders Recent Outputs.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff` vs the previously delivered archive: exactly one line added to
  `history.py` (the import); no other file changed.
