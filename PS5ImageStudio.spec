# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PS5 Image Studio (onedir, console).

  pyinstaller --noconfirm --clean PS5ImageStudio.spec

console=True is intentional: it lets crash tracebacks surface and gives the
re-exec'd "--job-runner" build subprocess real stdio pipes. lazy_mkpfs uses
multiprocessing, so run_studio.py calls multiprocessing.freeze_support().
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("customtkinter")        # themes/assets shipped by CTk

hiddenimports = []
hiddenimports += collect_submodules("lazy_mkpfs")
hiddenimports += collect_submodules("lazy_studio")
hiddenimports += ["customtkinter"]

# Optional fast backends + crypto — include if present in the build env.
for opt in ("isal", "zlib_ng", "cryptography"):
    try:
        __import__(opt)
        hiddenimports += collect_submodules(opt)
    except Exception:
        pass

a = Analysis(
    ["run_studio.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PS5ImageStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
    # console=False makes this a windowed (GUI) app, so launching it no longer
    # opens a black CMD window. The worker spawns the --job-runner subprocess
    # with CREATE_NO_WINDOW (see worker.py) so the now-consoleless parent doesn't
    # flash a console per build.
    # OSFMount (used during exFAT creation) requires elevation; without it the
    # mount fails with WinError 740. uac_admin embeds a requireAdministrator
    # manifest so Windows shows a UAC prompt at launch and the app — and the
    # --job-runner subprocess it spawns, which inherits the elevated token —
    # run elevated. The build re-execs sys.executable, so elevation propagates.
    uac_admin=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PS5ImageStudio",
)
