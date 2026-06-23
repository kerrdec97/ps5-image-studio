# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PS5 Image Studio — LINUX (experimental).

    pyinstaller --noconfirm --clean PS5ImageStudio_linux.spec

Differences from the Windows spec (PS5ImageStudio.spec):
  * console=True  — experimental Linux build keeps a console so early users can
                    copy/paste tracebacks into bug reports.
  * no uac_admin  — that's a Windows-only manifest option (OSFMount elevation).
                    On Linux the exFAT build uses losetup/mount and falls back to
                    sudo at runtime; there is no install-time elevation manifest.

Runtime system packages the Linux build shells out to (NOT bundled):
  * mkfs.exfat   -> exfatprogs        (sudo apt install exfatprogs)
  * losetup / mount / umount -> util-linux (usually preinstalled)
  * tkinter GUI  -> python3-tk        (sudo apt install python3-tk)
multiprocessing is used by lazy_mkpfs, so run_studio.py calls freeze_support().
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
    console=True,   # experimental Linux: surface tracebacks
    icon=None,
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
