# Linux Build & Run (Experimental)

Linux support is **experimental / community-tested**. Windows is the primary,
fully-supported platform.

## Runtime dependencies (system packages)

These are shelled out to at runtime and are **not** bundled in the build:

| Need | Package (Debian/Ubuntu) | Notes |
|---|---|---|
| GUI (tkinter) | `python3-tk` | Required to launch the app |
| `mkfs.exfat` | `exfatprogs` | Creates the exFAT filesystem |
| `losetup`, `mount`, `umount` | `util-linux` | Usually preinstalled |
| exFAT mount | `exfatprogs` or `exfat-fuse` | One of these |

```bash
sudo apt install python3-tk exfatprogs
# Fedora:  sudo dnf install python3-tkinter exfatprogs
# Arch:    sudo pacman -S tk exfatprogs
```

Python **3.10+** is required.

> **Privilege note:** building the exFAT image uses `losetup` and `mount`, which
> normally require root. The app tries without sudo first and falls back to
> `sudo`, so you may be prompted. Configure passwordless sudo for those commands
> or launch the app from a terminal where you can authenticate.

## Run from source (fastest)

```bash
python3 -m pip install -r requirements-studio.txt   # customtkinter
python3 run_studio.py --demo     # safe demo, no real files
python3 run_studio.py            # real builds
```

### One-shot scripts (Mint/Ubuntu — recommended)

Two helper scripts do everything for you (install system packages via apt, create
a local `.venv` to avoid the PEP 668 pip error, then run or build):

```bash
chmod +x run_linux.sh build_linux.sh   # first time only

./run_linux.sh --demo     # set up + LAUNCH from source (fastest test)
./run_linux.sh            # set up + launch (real builds)

./build_linux.sh          # set up + BUILD the standalone bundle + tar.gz
```

You can also double-click either script in the file manager and choose
"Run in Terminal".

## Build the bundle

```bash
./build_linux.sh
```

Produces `dist/PS5ImageStudio/PS5ImageStudio` and
`PS5ImageStudio-Linux-Experimental.tar.gz`.

The Linux build uses `PS5ImageStudio_linux.spec`, which differs from the Windows
spec only by dropping the Windows-only `uac_admin` manifest and setting
`console=True` (so early users can copy/paste tracebacks).

## What is NOT available on Linux yet

- **Edit exFAT Image** (the read-only mount/browse view) is **Windows-only** — it
  relies on OSFMount. On Linux the page shows a clear "Windows only" message.
  Building and compressing images works normally.
- **Post-queue Sleep/Shutdown**: the Windows commands are guarded; if you've asked
  for a post-queue action on Linux it is a no-op for this release (planned).

## Reporting a problem

Open Settings → **Copy debug info** and paste the result into your report, plus:

- Distro and version
- Kernel (`uname -a`)
- Python version (`python3 --version`)
- glibc (`ldd --version`)
- `logs/studio.log` and `logs/crash.log` (next to the app)
