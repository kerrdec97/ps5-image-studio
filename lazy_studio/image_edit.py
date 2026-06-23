"""Read-only mount/browse service for Edit exFAT Image mode (Slice A).

Headless orchestration — no UI. Mounts an existing .exfat image READ-ONLY via
OSFMount, lists its contents, reads properties, and unmounts with retry. It NEVER
writes: there is no replace/add/delete/expand/copy path here. The original image
cannot be modified — both because the mount is read-only (`-o ro`) and because no
write call exists in this module.

Does NOT touch create_exfat.py or the build pipeline; the OSFMount command shape
is replicated here deliberately (see the Slice A audit) to keep the proven build
path frozen.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Known OSFMount locations — same search the builder uses.
_OSF_PATHS = [
    r"C:\Program Files\OSFMount\osfmount.com",
    r"C:\Program Files (x86)\OSFMount\osfmount.com",
]
# Windows: keep child consoles hidden (matches create_exfat's format subprocess).
_NOWINDOW = 0x08000000 if os.name == "nt" else 0


def _hidden_startupinfo():
    """STARTUPINFO that hides the console window. osfmount.com is a .com console
    app; CREATE_NO_WINDOW alone can still flash a window, so we also force
    SW_HIDE via STARTF_USESHOWWINDOW. None on non-Windows."""
    if os.name != "nt":
        return None
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return si
    except Exception:
        return None


def _run_hidden(cmd):
    """Run a subprocess with the console fully suppressed (CREATE_NO_WINDOW +
    SW_HIDE). Used for EVERY OSFMount call in Edit mode. Read-only callers only —
    this never writes anything itself."""
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=_NOWINDOW, startupinfo=_hidden_startupinfo())


def find_osfmount() -> str | None:
    """Locate osfmount.com on PATH or in the known install dirs. None if absent."""
    found = shutil.which("osfmount.com")
    if found:
        return found
    for p in _OSF_PATHS:
        if os.path.exists(p):
            return p
    return None


def pick_free_letter(used: set[str] | None = None) -> str | None:
    """Return the first free drive letter in F..Z, or None if none are free.
    `used` may be injected for testing; otherwise probed from the filesystem."""
    if used is None:
        used = set()
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            try:
                if os.path.exists(f"{letter}:\\"):
                    used.add(letter)
            except Exception:
                used.add(letter)  # treat unprobeable letters as used (conservative)
    for letter in "FGHIJKLMNOPQRSTUVWXYZ":
        if letter not in used:
            return letter
    return None


@dataclass
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int = 0
    mtime: float = 0.0


@dataclass
class Properties:
    total: int = 0
    used: int = 0
    free: int = 0
    title: str = ""
    ppsa: str = ""
    version: str = ""
    content_id: str = ""
    has_param: bool = False


class MountError(RuntimeError):
    pass


@dataclass
class MountSession:
    """An active read-only mount. Holds the drive letter + the osfmount path so it
    can be unmounted. Created by mount_readonly(); never writes."""
    osfmount: str
    image: Path
    drive_letter: str

    @property
    def drive(self) -> str:
        return f"{self.drive_letter}:"

    @property
    def root(self) -> str:
        return f"{self.drive_letter}:\\"


def mount_readonly(image: str | Path) -> MountSession:
    """Mount an existing .exfat image READ-ONLY and return a MountSession.

    Raises MountError with a clear message if OSFMount is missing, no drive letter
    is free, the image doesn't exist, or the mount command fails.
    """
    img = Path(image)
    if not img.is_file():
        raise MountError(f"Image not found: {img}")
    osf = find_osfmount()
    if not osf:
        raise MountError("OSFMount is required to mount images, but it wasn't found. "
                         "Install OSFMount and try again.")
    letter = pick_free_letter()
    if not letter:
        raise MountError("No free drive letters are available to mount the image.")
    mount_point = f"{letter}:"
    # READ-ONLY mount. The -o ro flag is the OS-level guard; this module issuing no
    # write calls is the application-level guard.
    cmd = [osf, "-a", "-t", "file", "-f", str(img), "-m", mount_point, "-o", "ro"]
    try:
        res = _run_hidden(cmd)
    except Exception as e:
        raise MountError(f"Failed to launch OSFMount: {e}")
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "").strip()
        raise MountError(f"OSFMount could not mount the image (rc={res.returncode}). {detail}")
    return MountSession(osfmount=osf, image=img, drive_letter=letter)


def drive_alive(root: str | Path) -> bool:
    """True if the mounted drive is still present and usable. Used by the UI's
    health poll to detect an external unmount. Read-only: just an existence probe
    plus a disk_usage call."""
    try:
        p = Path(root)
        if not os.path.exists(str(p)):
            return False
        shutil.disk_usage(str(p))   # raises if the volume is gone
        return True
    except Exception:
        return False


def list_dir(path: str | Path) -> list[Entry]:
    """Shallow, read-only listing of one directory (lazy tree: callers expand
    folders on demand). Directories first, then files, both alphabetical."""
    entries: list[Entry] = []
    try:
        with os.scandir(str(path)) as it:
            for e in it:
                try:
                    is_dir = e.is_dir(follow_symlinks=False)
                    st = e.stat(follow_symlinks=False)
                    entries.append(Entry(name=e.name, path=e.path, is_dir=is_dir,
                                         size=0 if is_dir else st.st_size,
                                         mtime=st.st_mtime))
                except OSError:
                    entries.append(Entry(name=e.name, path=e.path, is_dir=False))
    except (OSError, FileNotFoundError):
        return []
    entries.sort(key=lambda x: (not x.is_dir, x.name.lower()))
    return entries


def read_properties(root: str | Path) -> Properties:
    """Capacity (disk_usage) + optional PS5 metadata from sce_sys/param.json.
    Read-only; never raises."""
    props = Properties()
    root_path = Path(root)
    try:
        usage = shutil.disk_usage(str(root_path))
        props.total, props.used, props.free = usage.total, usage.used, usage.free
    except Exception:
        pass
    # Optional PS5 dump metadata.
    try:
        param = root_path / "sce_sys" / "param.json"
        if param.is_file():
            from lazy_mkpfs.utils import read_param_json
            data = read_param_json(param)
            if isinstance(data, dict):
                props.has_param = True
                props.title = _title_from_param(data)
                props.content_id = _str_field(data, "contentId", "contentID")
                props.ppsa = _str_field(data, "titleId", "titleID") or _ppsa_from_cid(props.content_id)
                props.version = _extract_version(data)
    except Exception:
        pass
    return props


def unmount(session: MountSession, attempts: int = 5, delay: float = 1.0) -> tuple[bool, str]:
    """Detach the mount, retrying to ride out transient locks. Returns
    (ok, message). On persistent failure the message is actionable and includes
    the actual OSFMount stderr/stdout — no data is at risk (read-only), only the
    drive letter stays occupied."""
    last = ""
    for _ in range(max(1, attempts)):
        try:
            res = _run_hidden([session.osfmount, "-d", "-m", session.drive])
            if res.returncode == 0:
                return True, f"Unmounted {session.drive}"
            last = (res.stderr or res.stdout or "").strip()
        except Exception as e:
            last = str(e)
        time.sleep(delay)
    base = (f"Couldn't release {session.drive}. Close any Explorer windows or file "
            f"previews open on that drive, then try Unmount again.")
    return (False, f"{base}\nOSFMount said: {last}" if last else base)


# ── param.json helpers (read-only, mirror models._title_from_param_json) ─────
def _title_from_param(data: dict) -> str:
    loc = data.get("localizedParameters")
    if isinstance(loc, dict):
        dl = loc.get("defaultLanguage")
        if isinstance(dl, str):
            entry = loc.get(dl)
            if isinstance(entry, dict):
                t = entry.get("titleName")
                if isinstance(t, str) and t.strip():
                    return t.strip()
        for entry in loc.values():
            if isinstance(entry, dict):
                t = entry.get("titleName")
                if isinstance(t, str) and t.strip():
                    return t.strip()
    for key in ("titleName", "title"):
        t = data.get(key)
        if isinstance(t, str) and t.strip():
            return t.strip()
    return ""


def _extract_version(data: dict) -> str:
    """Pull the display version (e.g. '01.000.000') from PS5 param.json.

    Prefers the canonical version keys and NEVER returns versionFileUri (that's the
    update-package URL, not a version). Any candidate is validated against the
    NN.NNN.NNN shape so a stray URL/string can't slip through; if a candidate has
    a version embedded, that substring is used."""
    import re
    ver_re = re.compile(r"\d{2}\.\d{3}\.\d{3}")
    # Canonical order: masterVersion / contentVersion / version / appVer.
    # versionFileUri is deliberately excluded.
    for key in ("masterVersion", "contentVersion", "version", "appVer", "app_ver"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            s = v.strip()
            if ver_re.fullmatch(s):
                return s
            m = ver_re.search(s)   # tolerate wrappers, but only accept a real match
            if m:
                return m.group(0)
    return ""


def _str_field(data: dict, *keys: str) -> str:
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _ppsa_from_cid(content_id: str) -> str:
    """Content IDs embed the title id (e.g. 'EP1234-PPSA01234_00-...'); pull a
    PPSA-style token if present."""
    import re
    m = re.search(r"(PPSA\d{5})", content_id or "")
    return m.group(1) if m else ""
