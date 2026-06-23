"""BuildWorker: a single background thread (v1 = sequential, Concurrent jobs=1)
that drives builds and reports to the UI through an event queue.

Controls:
  submit(job)      enqueue a BuildJob
  pause()/resume() pause = stop pulling NEW jobs after the current one finishes
  stop_current()   cancel the running job between phases/files (terminate child,
                   delete the partial staging file — nothing reaches the archive)
  shutdown()       stop the thread

UI events (dicts) pushed to event_q:
  job_start, progress, log, phase, job_done, job_error, job_cancelled,
  paused, resumed, idle
"""
from __future__ import annotations
import contextlib
import io
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SHUTDOWN = object()


def phase_steps(job) -> list[str]:
    if getattr(job, "output_format", "ffpfsc") == "exfat":
        # exFAT-only: build the image and (optionally) move it. No compress,
        # no PFS verify (verify_pfs is PFS-only and would fail on raw exFAT).
        steps = ["Scan", "Create exFAT"]
        if job.ssd_staging and job.move_after:
            steps.append("Move")
        return steps
    if job.src_type == "folder" and job.exfat:
        steps = ["Scan", "Create exFAT", "Compress"]
    elif job.src_type == "folder":
        steps = ["Scan", "Compress"]
    else:
        steps = ["Scan", "Compress"]
    if job.verify:
        steps.append("Verify")
    if job.ssd_staging and job.move_after:
        steps.append("Move")
    return steps


def _map_token(token: str) -> str | None:
    t = (token or "").lower()
    if t in ("copy", "copying", "exfat"):
        return "Create exFAT"
    if t in ("compress", "compressing", "write", "writing", "encode"):
        return "Compress"
    return None


def _map_action(line: str) -> str | None:
    """Map a build log line to a short, human 'current action' string for the
    Active Build action tile. Purely additive: the line is still emitted as a
    normal log event regardless. Order matters — most specific substrings first
    so e.g. 'creating raw image' wins over a bare 'creating'."""
    low = (line or "").lower()
    # ordered (substring, action) pairs
    table = [
        ("analyzing folder", "Analyzing folder"),
        ("target exfat image size", "Creating image"),
        ("creating raw image", "Creating image"),
        ("creating temporary exfat", "Creating image"),
        ("syncing", "Syncing & unmounting"),
        ("unmounting", "Syncing & unmounting"),
        ("mounting", "Mounting image"),
        ("formatting", "Formatting exFAT"),
        ("copying", "Copying files"),
        ("wrapping", "Compressing"),
        ("verifying", "Verifying"),
        ("moving to archive", "Moving to archive"),
        ("successfully created", "Finalizing"),
    ]
    for needle, action in table:
        if needle in low:
            return action
    return None


class BuildWorker(threading.Thread):
    def __init__(self, event_q: "queue.Queue[dict]"):
        super().__init__(daemon=True)
        self.event_q = event_q
        self.pending: "queue.Queue" = queue.Queue()
        self.jobs_by_id: dict[str, object] = {}
        self._paused = threading.Event()
        self._cancel = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._announced_pause = False

    # ── public API ───────────────────────────────────────────
    def submit(self, job) -> None:
        self.jobs_by_id[job.id] = job
        self.pending.put(job.id)

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()
        self._emit(type="resumed")

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def stop_current(self) -> None:
        self._cancel.set()
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass

    def shutdown(self) -> None:
        self.pending.put(_SHUTDOWN)
        self.stop_current()

    # ── thread loop ──────────────────────────────────────────
    def _emit(self, **kw) -> None:
        self.event_q.put(kw)

    def run(self) -> None:
        while True:
            # Pause takes effect BETWEEN jobs.
            while self._paused.is_set():
                if not self._announced_pause:
                    self._emit(type="paused")
                    self._announced_pause = True
                time.sleep(0.2)
            self._announced_pause = False

            try:
                jid = self.pending.get(timeout=0.3)
            except queue.Empty:
                continue
            if jid is _SHUTDOWN:
                break
            job = self.jobs_by_id.get(jid)
            if job is None:
                continue
            self._cancel.clear()
            self._run_job(job)
            if self.pending.empty() and not self._paused.is_set():
                self._emit(type="idle")

    # ── one job ──────────────────────────────────────────────
    def _run_job(self, job) -> None:
        steps = phase_steps(job)
        self._emit(type="job_start", jid=job.id, steps=steps)
        cur_idx = 0

        def set_phase(label: str):
            nonlocal cur_idx
            if label in steps:
                cur_idx = steps.index(label)
                self._emit(type="phase", jid=job.id, label=label, idx=cur_idx, total=len(steps))

        out_path = job.build_output_path()
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._emit(type="job_error", jid=job.id, error=f"Cannot create staging folder: {e}")
            return

        if getattr(sys, "frozen", False):
            base = [sys.executable, "--job-runner"]      # re-exec the frozen exe
        else:
            base = [sys.executable, "-m", "lazy_studio.job_runner"]
        cmd = base + [
            "--src", job.src_path, "--out", str(out_path), "--type", job.src_type,
            "--output-format", getattr(job, "output_format", "ffpfsc"),
            "--backend", job.backend, "--level", str(job.level), "--cpu", str(job.cpu_count),
        ]
        if not job.exfat:
            cmd.append("--no-exfat")
        if not job.ram_streaming:
            cmd.append("--no-ram")

        self._emit(type="log", jid=job.id, line=f"$ build {job.display_name} → {out_path.name}")
        result = None
        # When the app is a windowed (console=False) build, a child process would
        # otherwise pop its own console window on Windows. CREATE_NO_WINDOW keeps
        # the --job-runner subprocess hidden. No-op (0) on non-Windows platforms.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            with self._lock:
                self._proc = subprocess.Popen(
                    cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=1, universal_newlines=True, creationflags=creationflags,
                )
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    self._emit(type="log", jid=job.id, line=line)
                    continue
                kind = ev.get("type")
                if kind == "progress":
                    mapped = _map_token(ev.get("phase", ""))
                    if mapped and mapped in steps and steps.index(mapped) != cur_idx:
                        set_phase(mapped)
                    self._emit(type="progress", jid=job.id, pct=ev.get("pct", 0.0),
                               phase=steps[cur_idx], idx=cur_idx, total=len(steps),
                               speed=ev.get("speed", ""), eta=ev.get("eta", ""))
                elif kind == "log":
                    txt = ev.get("line", "")
                    low = txt.lower()
                    if "pass 1" in low or "creating temporary exfat" in low or "exfat wrapper" in low:
                        set_phase("Create exFAT")
                    elif "pass 2" in low or "wrapping" in low:
                        set_phase("Compress")
                    self._emit(type="log", jid=job.id, line=txt)
                    # additive: surface a human 'current action' if this line maps
                    # to one. The log line above is emitted regardless.
                    action = _map_action(txt)
                    if action:
                        self._emit(type="action", jid=job.id, text=action)
                elif kind == "result":
                    result = ev
                elif kind == "error":
                    self._emit(type="log", jid=job.id, line="❌ " + ev.get("error", "error"))
            self._proc.wait()
        except Exception as e:
            self._emit(type="job_error", jid=job.id, error=str(e))
            with self._lock:
                self._proc = None
            return

        rc = self._proc.returncode if self._proc else 1
        with self._lock:
            self._proc = None

        # cancelled --------------------------------------------------
        if self._cancel.is_set():
            self._cleanup_partial(job, out_path)
            self._emit(type="job_cancelled", jid=job.id)
            return

        if rc != 0 or result is None:
            err = "Build failed"
            try:
                if self._proc and self._proc.stderr:
                    err = (self._proc.stderr.read() or err).strip().splitlines()[-1]
            except Exception:
                pass
            self._emit(type="job_error", jid=job.id, error=err)
            return

        # verify the freshly built STAGING image first; only move on success ----
        # exFAT output is never PFS-verified: verify_pfs is PFS-only and would
        # fail on a raw exFAT image. (A dedicated exFAT integrity check does not
        # exist yet.) The ffpfsc verify path below is unchanged.
        is_exfat_only = getattr(job, "output_format", "ffpfsc") == "exfat"
        if job.verify and not is_exfat_only:
            set_phase("Verify")
            self._emit(type="log", jid=job.id, line="🛡️ Verifying image…")
            self._emit(type="action", jid=job.id, text="Verifying")
            verify_ok, summary = self._verify(out_path, job=job, phase_label="Verify",
                                               phase_idx=cur_idx, total_steps=len(steps))
            for ln in summary:
                self._emit(type="log", jid=job.id, line=ln)
            if not verify_ok:
                self._emit(type="log", jid=job.id,
                           line=f"⚠️ Verification failed — image left in staging: {out_path}")
                self._emit(type="job_error", jid=job.id,
                           error=f"Verification failed ({out_path.name})")
                return
            self._emit(type="log", jid=job.id, line="✅ Verification passed")

        # move to archive (only after a successful build + verify) ----
        final_path = job.final_output_path()
        if str(final_path) != str(out_path):
            set_phase("Move")
            self._emit(type="log", jid=job.id, line=f"📦 Moving to archive → {final_path}")
            self._emit(type="action", jid=job.id, text="Moving to archive")
            try:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(out_path), str(final_path))
            except Exception as e:
                self._emit(type="job_error", jid=job.id, error=f"Move failed: {e}")
                return

        result["final_path"] = str(final_path)
        result["verify_ok"] = True
        # 'result' carries type="result" from the runner; strip it so it doesn't
        # collide with the type="job_done" kwarg below. The collision raises
        # TypeError, which the except handler turns into a false job_error —
        # flipping a successful build to FAILED and suppressing the modal.
        result_payload = dict(result)
        result_payload.pop("type", None)
        self._emit(type="job_done", jid=job.id, **result_payload)
        # Post-success cleanup: optionally delete the source. This runs AFTER
        # job_done is emitted (so the UI shows success immediately) and is fully
        # self-contained — it can never raise or flip the build to FAILED. It is
        # only reachable here, on the success fall-through; every failure path
        # (cancel/error/verify-fail/move-fail) returns before this point.
        self._maybe_delete_source(job, final_path)

    # ── helpers ──────────────────────────────────────────────
    def _maybe_delete_source(self, job, final_path) -> None:
        """Delete the source dump/image AFTER a fully successful build, if the
        user opted in. Fail-closed: every defensive check must pass or the source
        is kept and the reason logged. Never raises, never emits job_error — the
        build already succeeded; this is best-effort cleanup only.
        """
        try:
            if not getattr(job, "delete_source", False):
                return  # opt-in gate — not enabled, nothing to do (silent)

            src_raw = getattr(job, "src_path", "") or ""
            src_type = getattr(job, "src_type", "folder")

            def skip(reason: str):
                self._emit(type="log", jid=job.id,
                           line=f"ℹ️ Source not deleted ({reason}): {src_raw}")

            # 1. not cancelled (the only upstream cancel gate is before verify/move,
            #    so re-check here as a belt-and-suspenders).
            if self._cancel.is_set():
                return skip("build was cancelled")

            # 2. source must be a non-empty path
            if not src_raw:
                return skip("no source path")

            # Resolve both paths up front so symlinks/relative segments can't slip
            # past the containment checks below.
            try:
                src = Path(src_raw).resolve()
                final = Path(final_path).resolve()
            except Exception as e:
                return skip(f"path could not be resolved: {e}")

            # 3. final output must actually exist on disk (proof the build landed).
            if not final.exists():
                return skip("final output is missing")

            # 4. source must exist (nothing to delete otherwise).
            if not src.exists():
                return skip("source no longer exists")

            # 5. source must not BE the final output.
            if src == final:
                return skip("source is the final output")

            # 6. refuse root / drive-root / suspiciously shallow paths — a corrupt
            #    or empty src must never trigger a root deletion.
            if self._is_root_like(src):
                return skip("source resolves to a root/drive path")

            # 7. containment: the final output must NOT be inside the source (else
            #    deleting the source would destroy the just-built output), and the
            #    source must NOT be inside the final output, in either direction.
            if self._is_ancestor(src, final):
                return skip("final output is inside the source")
            if self._is_ancestor(final, src):
                return skip("source is inside the final-output path")

            # All checks passed — delete by source type.
            if src_type == "folder":
                if not src.is_dir():
                    return skip("source is not a folder")
                shutil.rmtree(str(src))   # no ignore_errors: surface partial failures
            else:  # exfat / ffpkg — single file
                if not src.is_file():
                    return skip("source is not a file")
                src.unlink()
            self._emit(type="log", jid=job.id, line=f"🗑️ Deleted source: {src}")
        except BaseException as e:  # noqa: BLE001 — must never propagate
            # The build already succeeded; a cleanup failure is a warning, not a
            # build failure. Log and swallow — never emit job_error, never raise.
            try:
                self._emit(type="log", jid=job.id,
                           line=f"⚠️ Could not delete source "
                                f"{getattr(job, 'src_path', '')}: {e}")
            except Exception:
                pass

    @staticmethod
    def _is_root_like(p: Path) -> bool:
        """True for filesystem roots / drive roots / paths too shallow to rmtree
        safely (e.g. C:\\, /, /home). Requires at least 2 path components below
        the anchor so a corrupt source can't wipe a drive or a top-level dir."""
        try:
            if p == p.parent:           # filesystem root
                return True
            if str(p) == p.anchor:      # drive root like C:\ or /
                return True
            # parts includes the anchor; require anchor + >=2 segments.
            meaningful = [seg for seg in p.parts if seg not in ("/", "\\", p.anchor)]
            return len(meaningful) < 2
        except Exception:
            return True  # fail closed

    @staticmethod
    def _is_ancestor(ancestor: Path, descendant: Path) -> bool:
        """True if `ancestor` is an ancestor of (or equal to) `descendant`.
        Both are expected already-resolved. Uses commonpath so it works across
        Python versions (no is_relative_to dependency)."""
        try:
            import os
            common = os.path.commonpath([str(ancestor), str(descendant)])
            return common == str(ancestor)
        except Exception:
            # Different drives / unrelated roots raise -> not an ancestor.
            return False

    def _cleanup_partial(self, job, out_path: Path) -> None:
        for p in (out_path,
                  out_path.parent / f"{job.ppsa}.exfat" if job.ppsa else None,
                  out_path.parent / "pfs_image.exfat"):
            if p is None:
                continue
            try:
                if p.exists():
                    p.unlink()
                    self._emit(type="log", jid=job.id, line=f"🧹 Removed partial {p.name}")
            except Exception:
                pass

    def _verify(self, path: Path, job=None, phase_label: str = "Verify",
                phase_idx: int = 0, total_steps: int = 0) -> tuple[bool, list[str]]:
        try:
            from lazy_mkpfs import verify_pfs
        except Exception as e:
            return False, [f"verify unavailable: {e}"]

        emit = self._emit
        jid = getattr(job, "id", None)

        class _LiveVerifyCapture:
            """Stand-in for stdout/stderr during verify_pfs. Collects ALL text for
            the final report, and parses the live carriage-return progress bar
            ("[███░░░] 43.2% verify") into worker progress events as it streams —
            instead of buffering everything until the call returns."""
            _PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*verify", re.IGNORECASE)

            def __init__(self):
                self.full = io.StringIO()   # everything, for report/log parsing
                self._buf = ""              # pending segment (split on \r and \n)
                self._last_emit = 0.0       # throttle progress events
                self._last_pct = -1.0

            def write(self, text):
                if not isinstance(text, str):
                    text = str(text)
                self.full.write(text)
                self._buf += text
                # Process completed segments delimited by \r (bar repaint) or \n.
                while "\r" in self._buf or "\n" in self._buf:
                    idx = min(i for i in (self._buf.find("\r"), self._buf.find("\n")) if i != -1)
                    seg, self._buf = self._buf[:idx], self._buf[idx + 1:]
                    self._scan(seg)
                return len(text)

            def _scan(self, seg):
                if not seg or jid is None:
                    return
                m = self._PCT_RE.search(seg)
                if not m:
                    return
                try:
                    pct = float(m.group(1)) / 100.0
                except ValueError:
                    return
                pct = max(0.0, min(1.0, pct))
                now = time.time()
                # Emit on a meaningful change, throttled to ~10/sec.
                if now - self._last_emit >= 0.1 or pct - self._last_pct >= 0.01:
                    self._last_emit = now
                    self._last_pct = pct
                    emit(type="progress", jid=jid, pct=pct, phase=phase_label,
                         idx=phase_idx, total=total_steps, speed="", eta="")

            def flush(self):
                pass

        cap = _LiveVerifyCapture()
        # verify_pfs runs in-process and signals real failure by raising
        # SystemExit(1); it returns normally on success. SystemExit derives from
        # BaseException (not Exception), so it must be caught explicitly.
        exit_code = 0
        crashed = None
        try:
            with contextlib.redirect_stdout(cap), contextlib.redirect_stderr(cap):
                verify_pfs(image=str(path), verbose=True)
        except SystemExit as se:
            exit_code = se.code if isinstance(se.code, int) else 1
        except Exception as e:  # any unexpected crash in the verifier = failure
            crashed = e

        # Lock the bar to 100% once the pass has finished (success path).
        if crashed is None and exit_code == 0 and jid is not None:
            emit(type="progress", jid=jid, pct=1.0, phase=phase_label,
                 idx=phase_idx, total=total_steps, speed="", eta="")

        lines = [ln.rstrip() for ln in cap.full.getvalue().splitlines() if ln.strip()]

        if crashed is not None:
            return False, (lines[-8:] + [f"verify error: {crashed}"]) if lines else [f"verify error: {crashed}"]

        # Authoritative signal: the verifier's own "Errors: N" tally.
        # Pass iff the process returned cleanly AND the parsed error count is 0.
        # Warnings are informational and never fail verification. The old naive
        # substring scan ("fail"/"error"/"mismatch"/❌) was removed — it matched
        # the literal "Errors: 0" success line and produced false failures.
        error_count = None
        for ln in lines:
            m = re.match(r"\s*Errors:\s*(\d+)\s*$", ln)
            if m:
                error_count = int(m.group(1))
                break

        ok = (exit_code == 0) and (error_count == 0 if error_count is not None else True)
        return ok, lines[-8:]
