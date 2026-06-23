#!/usr/bin/env bash
# =============================================================================
#  PS5 Image Studio — run from source on Linux (fastest way to test)
#
#  No PyInstaller build needed. Sets up a local venv, installs the GUI dep,
#  and launches the app.
#
#       chmod +x run_linux.sh     # first time only
#       ./run_linux.sh            # real builds
#       ./run_linux.sh --demo     # safe demo, no real files touched
#
#  (Target: Linux Mint / Ubuntu. Auto-installs python3-tk + exfatprogs via apt.)
# =============================================================================
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# System deps (Mint/Ubuntu): tkinter for the GUI, exfatprogs for real builds.
if command -v apt-get >/dev/null 2>&1; then
  NEED=()
  for p in python3 python3-venv python3-tk exfatprogs; do
    dpkg -s "$p" >/dev/null 2>&1 || NEED+=("$p")
  done
  if [ "${#NEED[@]}" -gt 0 ]; then
    say "Installing system packages: ${NEED[*]} (sudo)"
    sudo apt-get update -y && sudo apt-get install -y "${NEED[@]}"
  fi
fi
python3 -c "import tkinter" 2>/dev/null \
  || die "tkinter not importable — install your distro's python3-tk."

# venv (PEP 668 safe) + GUI dependency only (running from source needs just CTk).
#   Python venv ALWAYS makes a `lib64 -> lib` symlink, which exFAT/NTFS reject
#   ("Operation not permitted: lib64"). So if this drive has no symlink support,
#   we create the venv under $HOME (a real Linux fs) and reference it absolutely.
supports_symlinks() {
  local t="$1/.symlink_test_$$"
  if ln -s x "$t" 2>/dev/null; then rm -f "$t"; return 0; else rm -f "$t" 2>/dev/null; return 1; fi
}

LOCAL_VENV=".venv"
HOME_VENV="$HOME/.lazy_mkpfs_studio_venv/$(basename "$PWD")"

if [ -d "$LOCAL_VENV/bin" ]; then
  VENV="$LOCAL_VENV"
elif [ -d "$HOME_VENV/bin" ]; then
  VENV="$HOME_VENV"
elif supports_symlinks "$PWD"; then
  say "Creating virtualenv ./$LOCAL_VENV"
  python3 -m venv "$LOCAL_VENV" || die "venv creation failed."
  VENV="$LOCAL_VENV"
else
  warn "This drive doesn't support symlinks (exFAT/NTFS) — putting the venv under \$HOME:"
  warn "  $HOME_VENV"
  mkdir -p "$(dirname "$HOME_VENV")"
  python3 -m venv "$HOME_VENV" || die "venv creation failed under \$HOME too."
  VENV="$HOME_VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip >/dev/null
say "Ensuring GUI dependency (customtkinter)"
python -m pip install -r requirements-studio.txt

say "Launching PS5 Image Studio"
warn "(creating an exFAT image may prompt for sudo; Edit Image is Windows-only)"
exec python run_studio.py "$@"
