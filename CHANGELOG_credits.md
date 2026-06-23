# Lazy_MkPFS Studio — Credits & Support (Part D)

Scope: **`settings.py` only.** No pipeline/forbidden files touched. No default
behaviour changed.

## Change

Added a "Credits & Support" card at the bottom of the Settings page (grid row 8,
after Build Logs):

- "Thank you Nazky for the LazyMkPFS backend that powers this tool."
- "Support Nazky:" → clickable link **github.com/Nazky**
- "Support this project:" → clickable links **github.com/kerrdec97** ·
  **ko-fi.com/deckerr9746220**
- "Any support is massively appreciated."

Clickable links use the app's existing pattern (no native hyperlink widget exists
in CTk): an accent-coloured `CTkLabel` with `cursor="hand2"`, a hover colour
change, and a `<Button-1>` binding that calls `webbrowser.open(url)` on a
**hardcoded, trusted** URL. Opening is wrapped in try/except (`_open_url`) so a
missing browser or locked-down environment can never crash the app.

Added `import webbrowser` (Python stdlib — no new dependency) and two helpers
(`_open_url`, `_link`).

## Verification

- `python3 -m compileall lazy_studio lazy_mkpfs` → exit 0; `ast.parse` → OK.
- Xvfb smoke test (browser stubbed):
  - Credits card renders with the thank-you text, all three links, and the closing
    line; all pages still render.
  - Clicking each link opens the correct URL (github.com/Nazky,
    github.com/kerrdec97, ko-fi.com/deckerr9746220).
  - `_open_url` swallows a browser failure without raising.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff -rq` vs the previously delivered archive: only `settings.py` changed.
