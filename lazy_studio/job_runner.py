"""Subprocess entry point: builds ONE image via lazy_mkpfs and streams
machine-readable JSONL events on stdout so the GUI worker can drive the
Active Build screen. Run as:

    python -m lazy_studio.job_runner --src ... --out ... --type folder ...

Why a subprocess? lazy_mkpfs.pack_* are single blocking calls with no
cancellation hook. Running them in a child process lets the GUI terminate
the build between phases/files (Stop) and delete the partial staging file.
"""
from __future__ import annotations
import argparse
import json
import re
import sys

# real stdout captured BEFORE we redirect; events go here only.
_REAL_OUT = sys.stdout

PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
PHASE_RE = re.compile(r"%\s*([A-Za-z_]+)")
# Speed token may appear with an "@" prefix (compression bar: "@ 450MB/s") or
# without (exFAT copy bar: "│ 450.1MB/s │"). Match either. Requiring the "B/s"
# suffix keeps this from grabbing the compression "items/s" token or the
# "2.2GB/3.3GB" size ratio on the copy bar.
SPEED_RE = re.compile(r"@?\s*([\d.]+\s*[KMGT]?B/s)")
ETA_RE = re.compile(r"ETA\s*([0-9hms ]+)")


def emit(**kw) -> None:
    _REAL_OUT.write(json.dumps(kw) + "\n")
    _REAL_OUT.flush()


class _EventStream:
    """Stand-in for sys.stdout/stderr inside the child: parses the lazy_mkpfs
    progress bar (carriage-return updates) and verbose status lines, turning
    them into JSON events."""

    def __init__(self):
        self.buf = ""

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        self.buf += text
        while "\r" in self.buf or "\n" in self.buf:
            idx = min((self.buf.find(c) for c in "\r\n" if c in self.buf), default=-1)
            line, self.buf = self.buf[:idx], self.buf[idx + 1:]
            line = line.strip()
            if line:
                self._handle(line)

    def _handle(self, line):
        m = PCT_RE.search(line)
        is_bar = "%" in line and ("[" in line or "│" in line or "█" in line or "#" in line)
        if m and is_bar:
            pct = float(m.group(1)) / 100.0
            ph = PHASE_RE.search(line)
            sp = SPEED_RE.search(line)
            eta = ETA_RE.search(line)
            emit(type="progress", pct=pct,
                 phase=(ph.group(1) if ph else ""),
                 speed=(sp.group(1).replace(" ", "") if sp else ""),
                 eta=(eta.group(1).strip() if eta else ""))
        else:
            emit(type="log", line=line)

    def flush(self):
        pass

    def isatty(self):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--type", required=True, choices=["folder", "exfat", "ffpkg"])
    ap.add_argument("--output-format", default="ffpfsc", choices=["ffpfsc", "exfat"])
    ap.add_argument("--backend", default="zlib")
    ap.add_argument("--level", type=int, default=6)
    ap.add_argument("--cpu", type=int, default=0)
    ap.add_argument("--no-exfat", action="store_true")
    ap.add_argument("--no-ram", action="store_true")
    args = ap.parse_args()

    # Redirect everything lazy_mkpfs prints into the event stream.
    stream = _EventStream()
    sys.stdout = stream
    sys.stderr = stream

    try:
        # exFAT-only output: stop after building the exFAT image. Reuses the
        # existing create_exfat_image primitive directly (NOT pack_folder, which
        # would compress and then delete the exFAT in its finally block).
        if args.output_format == "exfat":
            import time as _time
            from pathlib import Path as _Path
            from lazy_mkpfs.create_exfat import create_exfat_image  # after redirect
            out_path = _Path(args.out)
            if out_path.suffix.lower() != ".exfat":
                out_path = out_path.with_suffix(".exfat")
            t0 = _time.time()
            create_exfat_image(args.src, out_path, verbose=True)
            elapsed = _time.time() - t0
            try:
                stored = out_path.stat().st_size
            except OSError:
                stored = 0
            # Count source files/bytes for the History record. exFAT is not
            # compressed, so there is NO meaningful gain — report 0 and let the
            # GUI display "—" rather than fabricate a compression ratio.
            src_bytes, src_files = 0, 0
            src_root = _Path(args.src)
            if src_root.is_dir():
                for f in src_root.rglob("*"):
                    try:
                        if f.is_file():
                            src_bytes += f.stat().st_size
                            src_files += 1
                    except OSError:
                        continue
            emit(type="result", gain=0.0, elapsed=round(elapsed, 2),
                 files=src_files, uncompressed=src_bytes, stored=stored,
                 output_format="exfat")
            sys.exit(0)

        from lazy_mkpfs import pack_folder, pack_file  # imported after redirect

        if args.type == "folder":
            stats = pack_folder(
                source_folder=args.src, output_image=args.out,
                zlib_level=args.level, zlib_backend=args.backend, cpu_count=args.cpu,
                use_ram_if_possible=not args.no_ram, verbose=True, exfat=not args.no_exfat,
            )
        else:
            stats = pack_file(
                source_file=args.src, output_image=args.out,
                zlib_level=args.level, zlib_backend=args.backend, cpu_count=args.cpu,
                use_ram_if_possible=not args.no_ram, verbose=True,
            )
        emit(type="result",
             gain=round(float(stats.actual_gain_pct), 2),
             elapsed=round(float(stats.elapsed_seconds), 2),
             files=int(stats.total_files),
             uncompressed=int(stats.uncompressed_total_size),
             stored=int(stats.stored_total_size))
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 - report everything to the GUI
        emit(type="error", error=str(e) or e.__class__.__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()
