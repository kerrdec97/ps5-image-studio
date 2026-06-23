# Lazy_MkPFS Studio — Queue KPI label polish

Scope: **`queue.py` only.** Presentational labels/units in the KPI strip. No
behaviour changed, no values recomputed, no defaults touched, no pipeline/forbidden
files touched.

## Change (file: `lazy_studio/pages/queue.py`, `_build_summary` tiles)

Shortened KPI tile labels and added units to the count tiles:

- "Total Waiting" → **Waiting**
- "Next Job" → **Next**
- "Batch Status" → **Status**
- "Queued" / "Paused" values now carry a unit with correct singular/plural:
  **"1 job"** / **"N jobs"** (was a bare number).
- "Waiting" already shows a unit via `human_size` (e.g. "208.5 GB") — unchanged.

The tile values still come from the same already-computed locals (`queued`,
`waiting_bytes`, `next_name`, `paused`, `batch_text`); only the label strings and
the two count value strings changed.

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb smoke test:
  - KPI strip renders: Queued "3 jobs", Waiting "208.5 GB", Next "ASTRO BOT",
    Paused "0 jobs", Status "Idle".
  - Singular case renders "1 job".
  - Old labels ("Total Waiting", "Next Job", "Batch Status") no longer present.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff -rq` vs the previously delivered archive: only `queue.py` changed.
