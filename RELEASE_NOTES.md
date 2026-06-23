# PS5 Image Studio v1.0

A desktop workstation for building and compressing PS5 game images
(exFAT and FFPFSC), powered by the LazyMkPFS backend.

**Windows** — primary, fully supported.
**Linux** — ⚠️ **experimental / community-tested.**

---

## Downloads

| Platform | File |
|---|---|
| Windows | `PS5ImageStudio-Windows.zip` |
| Linux (experimental) | `PS5ImageStudio-Linux-Experimental.tar.gz` |

---

## Windows

1. Download `PS5ImageStudio-Windows.zip` and extract it.
2. Run `PS5ImageStudio.exe`.

Windows will prompt for **administrator** rights — this is required because
OSFMount mounts the temporary disk image while the exFAT image is built.

---

## Linux — EXPERIMENTAL

Community-tested. Not every feature is available yet (see below). Please report
issues so we can improve Linux support.

**Required packages:**
```bash
sudo apt install python3-tk exfatprogs
#   python3-tk  -> GUI (tkinter)
#   exfatprogs  -> mkfs.exfat
#   losetup/mount come from util-linux (usually preinstalled)
```
Python **3.10+** required.

**Run:**
```bash
tar -xzf PS5ImageStudio-Linux-Experimental.tar.gz
cd PS5ImageStudio
./PS5ImageStudio
```

> **Privilege note:** creating the exFAT image uses `losetup`/`mount`, which need
> root. The app falls back to `sudo`, so you may be prompted. Configure sudo or
> run from a terminal where you can authenticate.

**Not available on Linux yet:**
- **Edit exFAT Image** (read-only mount/browse) — Windows-only (OSFMount). The page
  shows a clear message instead of failing. Building/compressing works normally.
- **Post-queue Sleep/Shutdown** — Windows-only for now (no-op on Linux).

---

## Please report (especially Linux)

Open **Settings → Copy debug info** and paste it into your report, plus:

- **Distro** and **version**
- **Kernel** — `uname -a`
- **Python version** — `python3 --version`
- **glibc** — `ldd --version`
- **Build log** — `logs/studio.log` (and `logs/crash.log` if present)

---

## Notes

- The build pipeline (exFAT creation, FFPFSC compression, verification) is shared
  across platforms; the Linux path uses `mkfs.exfat` + `losetup` + `mount`.
- This is a first cross-platform release — Windows and Linux users banging on it
  will surface far more than continued solo testing. Thank you for trying it.
