#!/usr/bin/env bash
# =============================================================================
#  PS5 Image Studio — one-shot Linux builder (tested target: Linux Mint / Ubuntu)
#
#  Just run it:
#       chmod +x build_linux.sh      # first time only
#       ./build_linux.sh
#
#  Or double-click it in the file manager and choose "Run in Terminal".
#
#  What it does, automatically:
#    1. Installs the system packages it needs (apt): python3-venv, python3-tk,
#       python3-pip, exfatprogs, util-linux  (asks for sudo once).
#    2. Creates a local virtualenv in ./.venv  (avoids the PEP 668
#       "externally-managed-environment" pip error on Mint/Ubuntu).
#    3. Installs the Python build deps + optional fast backends into the venv.
#    4. Runs PyInstaller with the Linux spec.
#    5. Produces  dist/PS5ImageStudio/PS5ImageStudio  and a .tar.gz.
#
#  Re-running is safe: it reuses the venv and only installs what's missing.
# =============================================================================
set -euo pipefail

# Always work from the directory this script lives in (so double-click works).
cd "$(dirname "$(readlink -f "$0")")"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. System packages (apt). Only the ones that are missing are installed.
# ---------------------------------------------------------------------------
APT_PKGS=(python3 python3-venv python3-pip python3-tk exfatprogs util-linux)

if command -v apt-get >/dev/null 2>&1; then
  MISSING=()
  for p in "${APT_PKGS[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p")
  done
  if [ "${#MISSING[@]}" -gt 0 ]; then
    say "Installing system packages: ${MISSING[*]}"
    warn "(you'll be asked for your password — this is the apt install)"
    sudo apt-get update -y
    sudo apt-get install -y "${MISSING[@]}"
  else
    say "All required system packages already installed."
  fi
else
  warn "apt-get not found — this script auto-installs on Debian/Ubuntu/Mint only."
  warn "Install these manually for your distro, then re-run:"
  warn "  python3 (3.10+), python3-venv, python3-pip, tkinter, exfatprogs, util-linux"
fi

# Sanity: tkinter must import (the GUI needs it).
python3 -c "import tkinter" 2>/dev/null \
  || die "tkinter still not importable. Install your distro's python3-tk package."

# ---------------------------------------------------------------------------
# 2. Virtualenv (the correct way around PEP 668 on Mint/Ubuntu).
#    NOTE: this project often lives on an exFAT/NTFS drive (for PS5 use). Python's
#    venv ALWAYS creates a `lib64 -> lib` symlink (even with --copies), and
#    exFAT/NTFS reject symlinks → "Operation not permitted: lib64". So we detect
#    whether the current drive supports symlinks; if not, we put the venv under
#    $HOME (a real Linux filesystem) and just reference it by absolute path. The
#    build still writes dist/ here (regular files, which exFAT handles fine).
# ---------------------------------------------------------------------------
supports_symlinks() {
  # $1 = directory to test. Returns 0 if a symlink can be created there.
  local t="$1/.symlink_test_$$"
  if ln -s x "$t" 2>/dev/null; then rm -f "$t"; return 0; else rm -f "$t" 2>/dev/null; return 1; fi
}

LOCAL_VENV=".venv"
HOME_VENV="$HOME/.lazy_mkpfs_studio_venv/$(basename "$PWD")"

# Reuse an existing venv if we already made one (either location).
if [ -d "$LOCAL_VENV/bin" ]; then
  VENV="$LOCAL_VENV"
elif [ -d "$HOME_VENV/bin" ]; then
  VENV="$HOME_VENV"
elif supports_symlinks "$PWD"; then
  say "Creating virtualenv in ./$LOCAL_VENV"
  python3 -m venv "$LOCAL_VENV" || die "venv creation failed."
  VENV="$LOCAL_VENV"
else
  warn "This drive doesn't support symlinks (exFAT/NTFS) — Python venv can't live here."
  warn "Creating the virtualenv under your home instead:"
  warn "  $HOME_VENV"
  mkdir -p "$(dirname "$HOME_VENV")"
  python3 -m venv "$HOME_VENV" || die "venv creation failed under \$HOME too."
  VENV="$HOME_VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip >/dev/null

# ---------------------------------------------------------------------------
# 3. Python build dependencies (into the venv).
# ---------------------------------------------------------------------------
say "Installing build dependencies (customtkinter, pyinstaller, cryptography)"
python -m pip install -r requirements-build.txt

say "Installing optional fast backends (best-effort — OK if these fail)"
python -m pip install isal zlib-ng 2>/dev/null || warn "optional backends skipped"

# ---------------------------------------------------------------------------
# 4. Build.
# ---------------------------------------------------------------------------
say "Running PyInstaller (PS5ImageStudio_linux.spec)"
pyinstaller --noconfirm --clean PS5ImageStudio_linux.spec

[ -x "dist/PS5ImageStudio/PS5ImageStudio" ] \
  || die "Build finished but the binary wasn't found at dist/PS5ImageStudio/."

# ---------------------------------------------------------------------------
# 5. Package.
# ---------------------------------------------------------------------------
say "Packaging tar.gz"
rm -f PS5ImageStudio-Linux-Experimental.tar.gz
tar -czf PS5ImageStudio-Linux-Experimental.tar.gz -C dist PS5ImageStudio

deactivate || true

printf '\n\033[1;32m============================  BUILD COMPLETE  ============================\033[0m\n'
cat <<'DONE'

  Run it:      ./dist/PS5ImageStudio/PS5ImageStudio --demo     (safe demo)
               ./dist/PS5ImageStudio/PS5ImageStudio            (real builds)

  Archive:     PS5ImageStudio-Linux-Experimental.tar.gz

  Note: creating an exFAT image uses losetup/mount and may prompt for sudo.
        Edit exFAT Image is Windows-only for now (it shows a message on Linux).

DONE
