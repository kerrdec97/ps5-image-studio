#!/usr/bin/env python3
"""Launch Lazy_MkPFS Studio.

    python run_studio.py            # real builds
    python run_studio.py --demo     # safe demo (no real files)

Also serves as the frozen-exe entry: when called with --job-runner it dispatches
to the build subprocess instead of opening the GUI.
"""
import datetime
import logging
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LOG_DIR = ROOT / "logs"


def _setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_DIR / "studio.log", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )


def _require_tk():
    """tkinter is a SYSTEM package on Linux (not pip-installable). Catch its
    absence early with a distro hint instead of a confusing ImportError deep in
    CustomTkinter."""
    try:
        import tkinter  # noqa: F401
    except Exception:
        print(
            "tkinter is not installed (required for the GUI).\n"
            "  Ubuntu/Debian:  sudo apt install python3-tk\n"
            "  Fedora:         sudo dnf install python3-tkinter\n"
            "  Arch:           sudo pacman -S tk"
        )
        sys.exit(1)


def _require_ctk():
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("CustomTkinter is not installed.\n  pip install customtkinter")
        sys.exit(1)


def _job_runner_mode() -> bool:
    """Frozen exe re-execs itself with --job-runner to run one build. Must NOT
    set up stdout logging here — job_runner streams JSONL on stdout."""
    if "--job-runner" in sys.argv:
        sys.argv.remove("--job-runner")
        from lazy_studio.job_runner import main as jr_main
        jr_main()
        return True
    return False


def main():
    if _job_runner_mode():
        return
    _setup_logging()
    _require_tk()
    _require_ctk()
    logging.info("Starting Lazy_MkPFS Studio (args=%s)", sys.argv[1:])
    try:
        from lazy_studio.app import main as app_main
        app_main()
    except Exception:
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / "crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n==== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ====\n")
            traceback.print_exc(file=f)
        logging.exception("FATAL")
        print("\n*** Fatal error — details written to logs\\crash.log ***")
        try:
            input("Press Enter to exit...")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # required: lazy_mkpfs uses multiprocessing
    main()
