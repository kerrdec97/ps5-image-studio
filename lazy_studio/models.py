"""State model: Settings, BuildJob, HistoryEntry, AppState + persistence helpers."""
from __future__ import annotations
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_DIR = Path.home() / ".lazy_mkpfs_studio"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
QUEUE_FILE = CONFIG_DIR / "queue.json"

BACKENDS = ["zlib", "zlib-ng", "isa-l"]
BACKEND_LABELS = {"zlib": "zlib", "zlib-ng": "zlib-ng", "isa-l": "Intel ISA-L"}
BACKEND_SHORT = {"zlib": "zlib", "zlib-ng": "zlib-ng", "isa-l": "ISA-L"}
COMP_WORKER_CHOICES = ["Auto", "4", "8", "12"]

TITLE_ID_RE = re.compile(r"(CUSA|PPSA|PCAS|PCJS|PCES|NPXS)\d{5}", re.IGNORECASE)
VERSION_RE = re.compile(r"(\d{2}\.\d{3}\.\d{3})")


# ───────────────────────── helpers ─────────────────────────

def human_size(num: float) -> str:
    if num <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit in ("B", "KB") else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def fmt_secs(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """Make a string safe for use as a filename component: strip characters that
    are illegal on Windows (\\ / : * ? \" < > |) and control chars, collapse
    whitespace to single underscores, and cap the length. Returns '' for input
    that reduces to nothing (caller decides how to handle that)."""
    if not name:
        return ""
    out = []
    for ch in name:
        if ch in '\\/:*?"<>|' or ord(ch) < 32:
            continue
        out.append(ch)
    cleaned = "".join(out)
    # collapse any run of whitespace to a single underscore
    cleaned = "_".join(cleaned.split())
    # trim leading/trailing dots and underscores (Windows dislikes trailing dots)
    cleaned = cleaned.strip("._")
    return cleaned[:max_len]


def system_debug_info(settings=None) -> str:
    """A plain-text block users can paste into a bug report: OS, Python,
    architecture, app version, and the current compression backend. Best-effort —
    never raises."""
    import platform as _pf
    import sys as _sys
    try:
        from . import __version__ as _ver
    except Exception:
        _ver = "?"
    lines = [
        "PS5 Image Studio — debug info",
        f"App version:  {_ver}",
        f"OS:           {_pf.system()} {_pf.release()}",
        f"OS detail:    {_pf.platform()}",
        f"Architecture: {_pf.machine()}",
        f"Python:       {_pf.python_version()} ({_sys.executable})",
    ]
    try:
        if hasattr(_pf, "libc_ver"):
            libc = _pf.libc_ver()
            if libc and libc[0]:
                lines.append(f"libc:         {libc[0]} {libc[1]}")
    except Exception:
        pass
    if settings is not None:
        try:
            be = BACKEND_SHORT.get(settings.backend, settings.backend)
            lines.append(f"Backend:      {be} L{settings.level}")
        except Exception:
            pass
    return "\n".join(lines)


def extract_title_id(text: str) -> str:
    m = TITLE_ID_RE.search(text)
    return m.group(0).upper() if m else ""


def extract_version(text: str) -> str:
    m = VERSION_RE.search(text)
    return m.group(1) if m else ""


def guess_title(path: Path, ppsa: str) -> str:
    name = path.stem
    name = re.sub(r"\(?\d{2}\.\d{3}\.\d{3}\)?", "", name)
    if ppsa:
        name = re.sub(re.escape(ppsa), "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").replace("-", " ").strip(" .-")
    return name or path.stem


def _title_from_param_json(path: Path) -> str:
    """Best-effort human title from a dump's sce_sys/param.json. Returns "" if the
    file is absent, unreadable, malformed, or carries no usable titleName.
    Reads only — never touches build/verify logic and never raises."""
    try:
        param = path / "sce_sys" / "param.json"
        if not param.is_file():
            return ""
        from lazy_mkpfs.utils import read_param_json
        data = read_param_json(param)
        if not isinstance(data, dict):
            return ""
        # PS5 shape: localizedParameters holds per-language entries (each with a
        # titleName) plus a defaultLanguage key pointing at the canonical entry.
        loc = data.get("localizedParameters")
        if isinstance(loc, dict):
            default_lang = loc.get("defaultLanguage")
            if isinstance(default_lang, str):
                entry = loc.get(default_lang)
                if isinstance(entry, dict):
                    t = entry.get("titleName")
                    if isinstance(t, str) and t.strip():
                        return t.strip()
            # fall back to any language entry that carries a titleName
            for entry in loc.values():
                if isinstance(entry, dict):
                    t = entry.get("titleName")
                    if isinstance(t, str) and t.strip():
                        return t.strip()
        # flat shapes some dumps use
        for key in ("titleName", "title"):
            t = data.get(key)
            if isinstance(t, str) and t.strip():
                return t.strip()
    except Exception:
        return ""
    return ""


def resolve_title(path: Path, ppsa: str) -> str:
    """Resolve a display title: prefer the real title in sce_sys/param.json,
    otherwise fall back to the folder-name heuristic. Safe on any input."""
    return _title_from_param_json(path) or guess_title(path, ppsa)


def dir_size(path: Path, cap_files: int = 200_000) -> tuple[int, int]:
    """Return (total_bytes, file_count). Walks with os.scandir; safe on huge trees."""
    total = 0
    count = 0
    stack = [str(path)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                            if count >= cap_files:
                                return total, count
                    except OSError:
                        continue
        except OSError:
            continue
    return total, count


# ───────────────────────── settings ─────────────────────────

@dataclass
class Settings:
    backend: str = "isa-l"
    level: int = 3
    comp_workers: str = "Auto"      # CPU/compression threads only ("Auto" | "4" | ...)
    concurrent_jobs: int = 1        # v1 worker is sequential; >1 reserved for later
    ram_streaming: bool = True
    ssd_staging: bool = True
    staging_path: str = str(Path.home() / "Stage")
    archive_path: str = str(Path.home() / "PS5" / "Images")
    move_after: bool = True
    verify: bool = True
    exfat: bool = True              # default exFAT wrapper -> .ffpfsc
    name_mode: str = "ppsa_title_version"   # output filename style (see BuildJob.out_name)
    delete_source: bool = False     # remembered default for the wizard toggle (OFF)
    first_run_seen: bool = False    # set once the first-run guidance has been shown
    save_logs: bool = False         # save a .txt build log per build (default OFF)
    logs_path: str = ""             # folder for saved logs ("" => <archive>/logs)
    post_queue_action: str = "nothing"   # "nothing" | "sleep" | "shutdown" after a clean queue

    def cpu_count(self) -> int:
        return 0 if self.comp_workers == "Auto" else int(self.comp_workers)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            known = {k: data[k] for k in data if k in cls.__dataclass_fields__}
            return cls(**known)
        except Exception:
            return cls()


# ───────────────────────── jobs ─────────────────────────

@dataclass
class BuildJob:
    src_path: str
    src_type: str                  # "folder" | "exfat" | "ffpkg"
    backend: str
    level: int
    cpu_count: int
    exfat: bool
    ssd_staging: bool
    staging_path: str
    archive_path: str
    move_after: bool
    verify: bool
    ram_streaming: bool

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    ppsa: str = ""
    version: str = ""
    size_bytes: int = 0
    file_count: int = 0

    status: str = "waiting"        # waiting|running|done|error|cancelled|paused
    phase: str = ""                # human phase label
    phase_idx: int = 0             # 0..len(PHASES)-1
    progress: float = 0.0          # 0..1 within current phase
    speed: str = ""
    eta: str = ""
    gain: float = 0.0
    elapsed: float = 0.0
    final_path: str = ""
    error: str = ""
    log: list[str] = field(default_factory=list)
    # Final deliverable format. "ffpfsc" = the proven compress/wrap pipeline
    # (exfat boolean below still selects .ffpfsc vs .ffpfs wrapper). "exfat" =
    # stop after creating the exFAT image, no compression. Default preserves
    # every existing job/saved-queue entry.
    output_format: str = "ffpfsc"
    # Output filename style: "ppsa" | "ppsa_title" | "ppsa_title_version".
    # Default preserves the original PPSA + Title + Version naming.
    name_mode: str = "ppsa_title_version"
    # When True, delete the source dump/image AFTER a fully successful build
    # (enforcement lives in the worker, added in a later slice). Default OFF —
    # destructive, so it must be explicitly enabled per job.
    delete_source: bool = False

    @property
    def out_ext(self) -> str:
        if self.output_format == "exfat":
            return ".exfat"
        return ".ffpfsc" if self.exfat else ".ffpfs"

    @property
    def out_name(self) -> str:
        mode = getattr(self, "name_mode", "ppsa_title_version")
        ver = f" ({self.version})" if self.version else ""
        if mode == "ppsa":
            stem = self.ppsa or Path(self.src_path).stem
        elif mode == "ppsa_title":
            stem = " ".join(b for b in (self.ppsa, self.title) if b).strip() \
                or Path(self.src_path).stem
        else:  # ppsa_title_version (default — original behaviour)
            bits = " ".join(b for b in (self.ppsa, self.title) if b).strip()
            stem = (bits or Path(self.src_path).stem) + ver
        return stem[:55] + self.out_ext

    @property
    def display_name(self) -> str:
        ver = f" ({self.version})" if self.version else ""
        return f"{self.title or Path(self.src_path).name}{ver}"

    @property
    def meta_line(self) -> str:
        return " · ".join(b for b in (self.ppsa, human_size(self.size_bytes), self.src_type) if b)

    def pipeline(self) -> list[tuple[str, str]]:
        """Return [(label, kind)] where kind in src|proc|out."""
        if self.output_format == "exfat" and self.src_type == "folder":
            return [("Dump folder", "src"), ("Create exFAT", "proc"), (".exfat", "out")]
        wrap = ("exFAT wrap" if self.exfat else "Pack PFS", "proc")
        out = (self.out_ext, "out")
        if self.src_type == "folder":
            return [("Dump folder", "src"), ("Create exFAT", "proc"),
                    ("Block-compress", "proc"), wrap, out]
        src = (".exfat image" if self.src_type == "exfat" else ".ffpkg image", "src")
        return [src, ("Block-compress", "proc"), wrap, out]

    def pipeline_short(self) -> str:
        if self.output_format == "exfat":
            return f"exFAT image · {Path(self.src_path).name}"[:40]
        return f"{BACKEND_SHORT[self.backend]} · L{self.level}" + (" · exFAT" if self.exfat else "")

    # path planning -------------------------------------------------
    def build_dir(self) -> Path:
        return Path(self.staging_path if self.ssd_staging else self.archive_path)

    def final_dir(self) -> Path:
        if self.ssd_staging and self.move_after:
            return Path(self.archive_path)
        return self.build_dir()

    def build_output_path(self) -> Path:
        return self.build_dir() / self.out_name

    def final_output_path(self) -> Path:
        return self.final_dir() / self.out_name


# ───────────────────────── history ─────────────────────────

@dataclass
class HistoryEntry:
    name: str
    ppsa: str = ""
    out_ext: str = ""
    sizes: str = "—"      # "37.2 → 19.8 GB"
    gain: str = "—"       # "46.8%"
    time: str = "—"       # "4m 12s"
    backend: str = ""     # "ISA-L L3"
    when: str = ""        # human timestamp
    final_path: str = ""
    src_path: str = ""
    src_type: str = "folder"
    log: list[str] = field(default_factory=list)
    outcome: str = "done"   # "done" | "error" | "cancelled" (old rows default to done)
    error: str = ""         # failure reason, when known
    log_path: str = ""      # path to the saved .txt build log, when one was written


def load_history() -> list[HistoryEntry]:
    try:
        data = json.loads(HISTORY_FILE.read_text())
        out = []
        for e in data:
            # Only pass keys that are actually present and non-null, so fields
            # added later (outcome, error) fall back to their dataclass defaults
            # for older history.json files rather than being forced to None.
            kw = {k: e[k] for k in HistoryEntry.__dataclass_fields__
                  if k in e and e[k] is not None}
            out.append(HistoryEntry(**kw))
        return out
    except Exception:
        return []


def save_history(entries: list[HistoryEntry]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def is_first_run() -> bool:
    """True when no settings file exists yet — i.e. the very first launch. Used to
    decide whether to show the onboarding guidance. Safe if the file already
    exists (returns False)."""
    try:
        return not SETTINGS_FILE.exists()
    except Exception:
        return False


def set_config_dir(path) -> None:
    """Repoint persistence at another folder (used by demo mode for isolation)."""
    global CONFIG_DIR, SETTINGS_FILE, HISTORY_FILE, QUEUE_FILE
    CONFIG_DIR = Path(path)
    SETTINGS_FILE = CONFIG_DIR / "settings.json"
    HISTORY_FILE = CONFIG_DIR / "history.json"
    QUEUE_FILE = CONFIG_DIR / "queue.json"


# ───────────────────────── queue persistence ─────────────────────────

_QUEUE_INIT_FIELDS = ("src_path", "src_type", "backend", "level", "cpu_count", "exfat",
                      "ssd_staging", "staging_path", "archive_path", "move_after", "verify",
                      "ram_streaming")
_QUEUE_EXTRA_FIELDS = ("title", "ppsa", "version", "size_bytes", "file_count", "output_format", "name_mode", "delete_source")


def save_queue(jobs: list[BuildJob]) -> None:
    """Persist waiting/paused jobs so the queue survives a restart."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = [{k: getattr(j, k) for k in (_QUEUE_INIT_FIELDS + _QUEUE_EXTRA_FIELDS)} for j in jobs]
    QUEUE_FILE.write_text(json.dumps(data, indent=2))


def load_queue() -> list[BuildJob]:
    try:
        data = json.loads(QUEUE_FILE.read_text())
    except Exception:
        return []
    out: list[BuildJob] = []
    for e in data:
        try:
            job = BuildJob(**{k: e[k] for k in _QUEUE_INIT_FIELDS})
            for extra in _QUEUE_EXTRA_FIELDS:
                if extra in e:
                    setattr(job, extra, e[extra])
            out.append(job)
        except Exception:
            continue
    return out


# ───────────────────────── app state ─────────────────────────

@dataclass
class AppState:
    settings: Settings = field(default_factory=Settings.load)
    jobs: list[BuildJob] = field(default_factory=list)
    history: list[HistoryEntry] = field(default_factory=load_history)
    active_job_id: str | None = None
    # Last terminal job (done/error/cancelled) for this session only — keeps its
    # own reference so the Active Build summary survives queue removal. Not persisted.
    last_finished: "BuildJob | None" = None
    # Queue-drain batch tracking (session-only, not persisted). batch_active is True
    # from the moment a batch starts until it drains; batch_tally accumulates outcome
    # counts; batch_summary holds the finished tally for the Queue page to display.
    batch_active: bool = False
    batch_tally: dict = field(default_factory=lambda: {"done": 0, "error": 0,
                                                        "cancelled": 0, "gain_sum": 0.0})
    batch_summary: dict | None = None

    def batch_begin(self) -> None:
        """Mark a new batch as started and clear any prior drain summary."""
        self.batch_active = True
        self.batch_tally = {"done": 0, "error": 0, "cancelled": 0, "gain_sum": 0.0}
        self.batch_summary = None

    def batch_record(self, outcome: str, gain: float = 0.0) -> None:
        """Accumulate one terminal outcome into the current batch tally."""
        if outcome in ("done", "error", "cancelled"):
            self.batch_tally[outcome] = self.batch_tally.get(outcome, 0) + 1
        if outcome == "done" and gain:
            self.batch_tally["gain_sum"] += gain

    def batch_maybe_drain(self) -> bool:
        """If a batch is active and no jobs remain active, finalize the summary
        once and return True. Otherwise return False."""
        if not self.batch_active:
            return False
        still_active = any(j.status in ("running", "waiting", "paused") for j in self.jobs)
        if still_active:
            return False
        t = self.batch_tally
        done = t.get("done", 0)
        self.batch_summary = {
            "done": done,
            "error": t.get("error", 0),
            "cancelled": t.get("cancelled", 0),
            "avg_gain": (t["gain_sum"] / done) if done else None,
        }
        self.batch_active = False
        return True

    def job(self, jid: str) -> BuildJob | None:
        return next((j for j in self.jobs if j.id == jid), None)

    def waiting(self) -> list[BuildJob]:
        return [j for j in self.jobs if j.status in ("waiting", "paused")]

    def running(self) -> BuildJob | None:
        return next((j for j in self.jobs if j.status == "running"), None)
