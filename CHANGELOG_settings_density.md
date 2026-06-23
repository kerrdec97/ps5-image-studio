# Lazy_MkPFS Studio — Settings density pass

Scope: **`settings.py` only.** No defaults changed. No setting behaviour changed.
No `theme.py`, no new font token. No `models.py` change. No pipeline/forbidden
files touched. Every setting and every help/recommendation/default value preserved.

## Problem

The Settings page was visually too tall: each setting rendered title, description,
"Recommended:" and "Current default:" as four separate stacked rows, plus generous
inter-row padding.

## Change (file: `lazy_studio/pages/settings.py`)

1. **Merged Recommended + Default onto one line.** "Recommended:" and the default
   now sit on a single row as **two side-by-side labels** — Recommended keeps its
   accent colour (`ACCENT_HI`), the default stays dim (`FG6`), separated by a "·".
   This removes one physical row per setting with no information loss. Applied via:
   - a new `_rec_default(parent, row, rec, default, pad)` helper for the
     hand-built Compression card (Backend + Level blocks), and
   - inline two-label rendering inside the shared `_row()` helper for the other
     settings.
2. **Tightened padding only:**
   - `_row` bottom gap `12 → 8`; row separator gap `12 → 8`.
   - card header `(16,10) → (14,8)`; card-to-card gap `12 → 10`.
   - Compression block internal gaps trimmed (level header `14 → 10`, final SegBar
     `(8,16) → (0,14)`, help-line pads consolidated).
   - SSD staging paths frame `(12,12) → (8,10)`.

Net: roughly one fewer row per setting plus reduced padding — a noticeably shorter
page with all text intact and colour emphasis preserved.

## Preservation guarantees (verified)

- **`_set` is byte-identical** and all 11 control wirings are intact (backend,
  level, comp_workers, concurrent_jobs, ram_streaming, ssd_staging, staging_path,
  archive_path, move_after, verify, name_mode).
- **All `rec=`/`default=` values are byte-identical** to the previous version
  (diff of the kwargs is empty); all descriptions and all 9 setting titles are
  preserved.
- **`models.py` is byte-identical** — defaults untouched.

## One intentional wording trim (flagged)

To fit the merged line, the label prefix "**Current default:**" was shortened to
"**Default:**". The default **value** is unchanged in every case (e.g.
"Default: Intel ISA-L", "Default: 3", "Default: Auto",
"Default: PPSA + Title + Version"); only the redundant word "Current" was dropped.
If you'd prefer the literal "Current default:" prefix back, it's a one-line change
in `_rec_default` and `_row`.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb smoke test:
  - 9 "Recommended:" + 9 "Default:" lines render (one per setting, both compression
    blocks included); default values preserved (Intel ISA-L, 3, Auto,
    PPSA + Title + Version); all 5 sections present.
  - **Settings object unchanged by rendering** (before == after snapshot).
  - **`_set` applies and restores** a value correctly.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `models.py` byte-identical; `diff -rq` confirms only `settings.py` changed.
