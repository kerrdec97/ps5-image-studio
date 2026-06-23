# Lazy_MkPFS Studio — Linux experimental release prep

Scope: 5 modified files (`models.py`, `pages/edit_image.py`, `pages/home.py`,
`pages/settings.py`, `run_studio.py`) + 4 new files (Linux spec, build script,
docs). No pipeline/forbidden files touched. No Windows behaviour changed (all
platform branches are guarded). The build pipeline already supports Linux
(`mkfs.exfat`/`losetup`/`mount`), so no frozen-file changes were needed.

## 1. Edit Image — Linux guard

`pages/edit_image.py`: `_render()` now checks the platform first. On non-Windows it
shows a clear "Edit Image is Windows-only for now" card (explaining OSFMount /
that building & compressing still work) instead of attempting an OSFMount that can
only fail. On Windows the normal Edit UI is unchanged. `pages/home.py`: the Edit
tile subtitle reads "Windows only for now" on non-Windows.

## 2. tkinter dependency check

`run_studio.py`: new `_require_tk()` (called before `_require_ctk()`), catches a
missing `tkinter` and prints distro-specific install hints (Debian/Ubuntu, Fedora,
Arch) instead of a confusing ImportError. tkinter is a system package on Linux, not
pip-installable.

## 3. Linux packaging

- `LazyMkPFSStudio_linux.spec`: the Windows spec minus the Windows-only `uac_admin`
  manifest, with `console=True` (experimental Linux surfaces tracebacks).
- `build_linux.sh`: checks tkinter, installs build deps, runs PyInstaller with the
  Linux spec, and produces `LazyMkPFSStudio-Linux-Experimental.tar.gz`.

## 4. Release docs

- `BUILD_LINUX.md`: runtime packages, run-from-source, build steps, what's not yet
  available, and what to include in a bug report.
- `RELEASE_NOTES.md`: GitHub release wording — Windows (supported) + Linux
  (experimental), required packages, sudo note, and the report checklist.

## Bonus — Copy debug info

`models.py`: new `system_debug_info()` (OS, OS detail, architecture, Python, libc,
app version, backend). `pages/settings.py`: a "📋 Copy debug info" button in the
Credits & Support card copies it to the clipboard — makes Linux bug reports far
easier.

## Verification

- `compileall` + `ast` on all edited files and the Linux spec → clean;
  `bash -n build_linux.sh` → clean.
- Xvfb tests:
  - Edit Image: on Linux shows the Windows-only message and no Open CTA; with
    `sys.platform` patched to win32 it shows the normal Edit UI (Open .exfat +
    Mount Read-Only) — guard does not affect Windows.
  - tkinter check: silent when present; exits with the install hint when missing.
  - `system_debug_info` includes version/OS/arch/Python/backend; the Copy button
    populates the clipboard.
  - Full page-render regression (all 7 pages + home) clean.
- Forbidden-file SHA-256 checksums identical to input (all 6 OK).
- `diff -rq` vs prior archive: exactly the 5 modified + 4 new files, nothing else.

Note: actual Linux packaging (`build_linux.sh` → PyInstaller) and the real exFAT
build path must be exercised on a Linux machine; this environment verifies the UI
guards, the dependency check, the spec/script syntax, and that Windows is
unaffected.
