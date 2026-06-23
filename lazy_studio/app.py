"""App shell: titlebar + sidebar nav (CTkFrame page swapping) + event pump."""
from __future__ import annotations
import queue
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import customtkinter as ctk

from . import theme as T
from . import models as M
from .worker import BuildWorker
from .demo import DemoWorker, DEMO_SPECS
from .pages.dashboard import DashboardPage
from .pages.queue import QueuePage
from .pages.active_build import ActiveBuildPage
from .pages.history import HistoryPage
from .pages.settings import SettingsPage
from .pages.home import HomeFrame
from .pages.build_wizard import BuildWizardPage
from .pages.edit_image import EditImagePage


class App(ctk.CTk):
    def __init__(self, demo=False):
        super().__init__()
        ctk.set_appearance_mode("dark")
        T.init_fonts()
        self.demo = demo
        self.title("PS5 Image Studio — DEMO" if demo else "PS5 Image Studio")
        self.geometry("1320x860")
        self.minsize(1100, 720)
        self.configure(fg_color=T.BG1)

        if demo:
            import shutil
            import tempfile
            d = Path(tempfile.gettempdir()) / "lazy_mkpfs_studio_demo"
            shutil.rmtree(d, ignore_errors=True)   # fresh each launch
            M.set_config_dir(d)

        # Detect first run BEFORE anything can write the settings file. Settings.load
        # only reads, but capture here so the check is unambiguous.
        self._is_first_run = M.is_first_run()
        self.appstate = M.AppState()
        self.appstate.jobs.extend(M.load_queue())   # restore queue from last session
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.worker = (DemoWorker if demo else BuildWorker)(self.events)
        self.worker.start()
        self._submitted: set[str] = set()
        self._run_start = 0.0
        self._current = "dashboard"
        self._demo_i = 0
        # Post-queue (sleep/shutdown) countdown state — set while a countdown is live.
        self._pq_win = None
        self._pq_after = None
        self._pq_remaining = 0
        # Closing-dialog state.
        self._closing = False
        self._close_win = None

        self._build_titlebar()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        body = self.body
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Mode-based UI: no sidebar. Content fills the full width directly (it used
        # to sit in column 1 beside the sidebar; the sidebar has been removed).
        self.content = ctk.CTkFrame(body, fg_color=T.BG1, corner_radius=0)
        self.content.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages = {}
        page_classes = {"dashboard": DashboardPage, "queue": QueuePage,
                        "active": ActiveBuildPage, "history": HistoryPage, "settings": SettingsPage,
                        "build": BuildWizardPage, "edit": EditImagePage}
        for key, cls in page_classes.items():
            try:
                self.pages[key] = cls(self.content, self)
                self.pages[key]._page_key = key
            except Exception:
                logging.exception("Failed to build page %r", key)
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")

        if self.demo:
            self._seed_demo()
        # Home is a full-window sibling layered over the body. Show it first; the
        # body (sidebar + pages) is revealed only when a mode is entered. Pages are
        # still instantiated above, so nothing about their init is deferred.
        self.home = HomeFrame(self, self)
        self._current = "dashboard"   # default target once a mode is entered
        self.go_home()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._pump)
        # First-run guidance: show once, non-blocking, after the window has settled.
        # Skipped if the user has already seen it (flag) or in demo mode.
        if self._is_first_run and not getattr(self.appstate.settings, "first_run_seen", False) \
                and not self.demo:
            self.after(400, self._maybe_show_onboarding)

    def _maybe_show_onboarding(self):
        try:
            from .onboarding import show_onboarding
            show_onboarding(self)
        except Exception:
            logging.exception("onboarding failed")

    # ── chrome ────────────────────────────────────────────────
    def _build_titlebar(self):
        bar = ctk.CTkFrame(self, fg_color=T.BG4, corner_radius=0, height=38)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="🎮", font=T.F["icon"]).pack(side="left", padx=(14, 8))
        ctk.CTkLabel(bar, text="PS5 Image Studio", font=T.F["bodyb"], text_color=T.FG1).pack(side="left")
        ctk.CTkLabel(bar, text="— PS5 Image Workstation · v1.0", font=T.F["meta"],
                     text_color=T.FG6).pack(side="left", padx=8)
        if getattr(self, "demo", False):
            ctk.CTkLabel(bar, text="DEMO — no real files touched", font=T.F["meta"],
                         text_color="#000", fg_color=T.WARN, corner_radius=999,
                         padx=10, pady=2).pack(side="left", padx=8)
        # The titlebar return-to-Home control was removed: every workspace page now
        # carries a prominent top-left "🏠 Home" button (home_btn_large), so the
        # small titlebar duplicate was redundant and visually confusing. The toggles
        # that used to show/hide it in enter_mode()/go_home() are gone too.

    def _refresh_meters(self):
        # No-op retained intentionally. The sidebar storage meters were removed in
        # the mode-based UI migration (Overview now shows storage info), but
        # _refresh_data still calls this after every job event — keeping it as a
        # harmless no-op avoids touching that flow.
        return

    # ── navigation ────────────────────────────────────────────
    def enter_mode(self, key):
        """Leave Home and enter the shell at the given page. Separate from
        show_page so Home never goes through the sidebar highlight loop."""
        self.home.pack_forget()
        if not self.body.winfo_ismapped():
            self.body.pack(fill="both", expand=True)
        self.show_page(key)

    def go_home(self):
        """Return to the Home mode-select screen (hides the shell body)."""
        self.body.pack_forget()
        self.home.pack(fill="both", expand=True)

    def show_page(self, key):
        if key not in self.pages:
            logging.error("page %r unavailable", key)
            return
        # Mode-based UI: every page runs full-width (content is gridded full-width
        # at creation; there is no sidebar). Navigation happens via Home + each
        # page's own "🏠 Home" header.
        selected = self.pages[key]
        # Hard swap: hide every page frame, then grid only the selected one.
        # tkraise() alone is unreliable here because the pages are
        # CTkScrollableFrames and do not stack predictably.
        for page in self.pages.values():
            page.grid_remove()
        selected.grid(row=0, column=0, sticky="nsew")
        self.update_idletasks()
        self._current = key
        selected.on_show()

    # ── job lifecycle ─────────────────────────────────────────
    def add_job(self, job: M.BuildJob, start=False):
        self.appstate.jobs.append(job)
        self._refresh_data()
        if start:
            self.start_queue()

    # ── demo mode ─────────────────────────────────────────────
    def _make_demo_job(self, spec, outcome="ok"):
        import random
        s = self.appstate.settings
        job = M.BuildJob(src_path=f"(demo) {spec['ppsa']}", src_type="folder", backend=s.backend,
                         level=s.level, cpu_count=s.cpu_count(), exfat=s.exfat, ssd_staging=s.ssd_staging,
                         staging_path=s.staging_path, archive_path=s.archive_path,
                         move_after=s.move_after, verify=s.verify, ram_streaming=s.ram_streaming)
        job.title, job.ppsa, job.version = spec["title"], spec["ppsa"], spec["version"]
        job.size_bytes, job.file_count = spec["size"], random.randint(900, 2200)
        job.demo_outcome = outcome
        return job

    def add_demo_job(self):
        spec = DEMO_SPECS[self._demo_i % len(DEMO_SPECS)]
        self._demo_i += 1
        self.add_job(self._make_demo_job(spec, "ok"))

    def _seed_demo(self):
        for spec, gain, t in ((DEMO_SPECS[0], "46.8%", "4m 12s"), (DEMO_SPECS[4], "42.7%", "11m 47s")):
            self.appstate.history.append(M.HistoryEntry(
                name=spec["title"], ppsa=spec["ppsa"], out_ext=".ffpfsc",
                sizes=f"{M.human_size(spec['size'])} → {M.human_size(int(spec['size']*0.56))}",
                gain=gain, time=t, backend="ISA-L L3", when="demo", final_path="",
                src_path=f"(demo) {spec['ppsa']}", src_type="folder", log=["(demo build log)"]))
        M.save_history(self.appstate.history)
        self.appstate.jobs.append(self._make_demo_job(DEMO_SPECS[1], "ok"))
        self.appstate.jobs.append(self._make_demo_job(DEMO_SPECS[2], "verify_fail"))
        self._demo_i = 3

    def add_job_from_path(self, path: str, src_type: str | None = None, start=False):
        p = Path(path)
        if src_type is None:
            ext = p.suffix.lower()
            src_type = "exfat" if ext == ".exfat" else ("ffpkg" if ext == ".ffpkg" else "folder")
        s = self.appstate.settings
        job = M.BuildJob(src_path=str(p), src_type=src_type, backend=s.backend, level=s.level,
                         cpu_count=s.cpu_count(), exfat=s.exfat, ssd_staging=s.ssd_staging,
                         staging_path=s.staging_path, archive_path=s.archive_path,
                         move_after=s.move_after, verify=s.verify, ram_streaming=s.ram_streaming)
        job.ppsa = M.extract_title_id(str(p))
        job.version = M.extract_version(p.name)
        job.title = M.resolve_title(p, job.ppsa)
        self.appstate.jobs.append(job)

        def work():
            try:
                if p.is_dir():
                    size, files = M.dir_size(p)
                elif p.is_file():
                    size, files = p.stat().st_size, 1
                else:
                    size, files = 0, 0
            except OSError:
                size, files = 0, 0
            # route back to the main thread via the event queue (no Tk calls off-thread)
            self.events.put({"type": "job_meta", "jid": job.id, "size": size, "files": files})
        import threading
        threading.Thread(target=work, daemon=True).start()
        self._refresh_data()
        if start:
            self.start_queue()

    def start_queue(self):
        self.worker.resume()
        started = False
        for j in self.appstate.jobs:
            if j.status == "waiting" and j.id not in self._submitted:
                self._submitted.add(j.id)
                self.worker.submit(j)
                started = True
        if started:
            self.appstate.batch_begin()
        self._refresh_data()
        if started:
            # Jump to the live view so the user sees the build they just started.
            self.show_page("active")

    def toggle_pause(self):
        if self.worker.is_paused():
            self.worker.resume()
        else:
            self.worker.pause()
        self._refresh_data()

    def stop_current(self):
        self.worker.stop_current()

    def remove_job(self, jid):
        j = self.appstate.job(jid)
        if j and j.status in ("waiting", "paused", "error", "cancelled", "done"):
            self.appstate.jobs.remove(j)
            self._submitted.discard(jid)
            self._refresh_data()

    def move_job_up(self, jid):
        jobs = self.appstate.jobs
        idx = next((i for i, j in enumerate(jobs) if j.id == jid), None)
        if idx and idx > 0 and jobs[idx].id not in self._submitted:
            jobs[idx - 1], jobs[idx] = jobs[idx], jobs[idx - 1]
            self._refresh_data()

    # ── event pump ────────────────────────────────────────────
    def _pump(self):
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        # live elapsed
        run = self.appstate.running()
        if run and self._run_start:
            run.elapsed = time.time() - self._run_start
            if self._current == "active":
                self.pages["active"].tile_elapsed.set(M.fmt_secs(run.elapsed))
        self.after(100, self._pump)

    def _handle(self, ev):
        t = ev.get("type")
        jid = ev.get("jid")
        job = self.appstate.job(jid) if jid else None

        if t == "job_start" and job:
            # A new build starting means the queue isn't actually finished — cancel
            # any pending post-queue (sleep/shutdown) countdown.
            self._cancel_post_queue_countdown()
            job.status = "running"
            job.phase = "Scan"
            job.phase_idx = 0
            job._steps = ev.get("steps", ["Scan", "Compress", "Verify", "Move"])
            job.progress = 0.0
            self.appstate.active_job_id = jid
            self._run_start = time.time()
            self.pages["active"].set_steps(job, job._steps)
            self._refresh_data()
        elif t == "progress" and job:
            job.progress = ev.get("pct", 0.0)
            job.speed = ev.get("speed", "")
            job.eta = ev.get("eta", "")
            job.phase = ev.get("phase", job.phase)
            job.phase_idx = ev.get("idx", job.phase_idx)
            self.pages["queue"].update_progress(job)
            self.pages["active"].update_progress(job)
        elif t == "phase" and job:
            job.phase = ev.get("label", job.phase)
            job.phase_idx = ev.get("idx", job.phase_idx)
            self.pages["active"].set_phase(job)
            self.pages["queue"].update_progress(job)
        elif t == "log" and job:
            job.log.append(ev.get("line", ""))
            self.pages["active"].add_log(job, ev.get("line", ""))
        elif t == "action" and job:
            self.pages["active"].set_action(job, ev.get("text", ""))
        elif t == "job_done" and job:
            job.status = "done"
            job.gain = ev.get("gain", 0.0)
            job.elapsed = ev.get("elapsed", job.elapsed)
            job.progress = 1.0
            job.final_path = ev.get("final_path", "")
            self.appstate.last_finished = job
            self._record_history(job, ev)
            self.appstate.batch_record("done", job.gain)
            drained = self.appstate.batch_maybe_drain()
            self.pages["active"].on_done(job)
            self._run_start = 0.0
            self._refresh_data()
            self._show_completion_modal(job)
            if drained:
                self._on_queue_drained()
        elif t == "job_error" and job:
            job.status = "error"
            job.error = ev.get("error", "")
            job.log.append("❌ " + job.error)
            self.appstate.last_finished = job
            self.pages["active"].add_log(job, "❌ " + job.error)
            self._record_history(job, ev, outcome="error")
            self.appstate.batch_record("error")
            drained = self.appstate.batch_maybe_drain()
            self._run_start = 0.0
            self._refresh_data()
            if drained:
                self._on_queue_drained()
        elif t == "job_cancelled" and job:
            job.status = "cancelled"
            job.log.append("⏹ Cancelled")
            self.appstate.last_finished = job
            self._record_history(job, ev, outcome="cancelled")
            self.appstate.batch_record("cancelled")
            drained = self.appstate.batch_maybe_drain()
            self._run_start = 0.0
            self._refresh_data()
            if drained:
                self._on_queue_drained()
        elif t == "job_meta" and job:
            job.size_bytes = ev.get("size", job.size_bytes)
            job.file_count = ev.get("files", job.file_count)
            self._refresh_data()
        elif t in ("paused", "resumed", "idle"):
            self._refresh_data()

    def _record_history(self, job, ev, outcome="done"):
        # Only present real size/gain figures. On failure/cancel these are often
        # partial or unavailable — leave them blank rather than fabricate "0 → 0".
        unc = ev.get("uncompressed", job.size_bytes) if ev else job.size_bytes
        stored = ev.get("stored", 0) if ev else 0
        # exFAT output is not compressed, so the usual raw→stored / gain% / backend
        # columns are misleading. Detect it and show role-appropriate text instead.
        is_exfat = getattr(job, "output_format", "ffpfsc") == "exfat" or job.out_ext == ".exfat"
        if outcome == "done" and stored:
            if is_exfat:
                sizes = f"{M.human_size(stored)} exFAT image"
                gain = "—"
            else:
                sizes = f"{M.human_size(unc)} → {M.human_size(stored)}"
                gain = f"{job.gain:.1f}%"
        else:
            sizes = f"{M.human_size(unc)} → —" if unc else "—"
            gain = "—"
        backend = "exFAT" if is_exfat else f"{M.BACKEND_SHORT[job.backend]} L{job.level}"
        entry = M.HistoryEntry(
            name=job.title or Path(job.src_path).name,
            ppsa=job.ppsa,
            out_ext=job.out_ext,
            sizes=sizes,
            gain=gain,
            time=M.fmt_secs(job.elapsed),
            backend=backend,
            when=datetime.now().strftime("%b %d, %H:%M"),
            final_path=job.final_path,
            src_path=job.src_path,
            src_type=job.src_type,
            log=list(job.log[-200:]),
            outcome=outcome,
            error=getattr(job, "error", "") or "",
        )
        # Optionally save the full build log to a .txt file (default OFF). Wrapped so
        # any failure (permissions, bad path, disk full) is swallowed and never
        # affects the build/history flow. Sets log_path on both the history entry
        # and the live job (so Overview's last_finished can open it too).
        log_path = self._write_build_log(job, entry, outcome, sizes, gain)
        if log_path:
            entry.log_path = log_path
            try:
                job.log_path = log_path
            except Exception:
                pass
        self.appstate.history.insert(0, entry)
        M.save_history(self.appstate.history)

    def _write_build_log(self, job, entry, outcome, sizes, gain) -> str:
        """Write a metadata header + full build log to a .txt file when the
        save_logs setting is on. Returns the written path, or '' on failure / when
        disabled. Never raises — build flow must not depend on this."""
        s = self.appstate.settings
        if not getattr(s, "save_logs", False):
            return ""
        try:
            folder = Path(s.logs_path) if getattr(s, "logs_path", "") else \
                Path(s.archive_path) / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            ppsa = M.sanitize_filename(job.ppsa) or "NOID"
            title = M.sanitize_filename(job.title or Path(job.src_path).name)
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            parts = [p for p in (ppsa, title, stamp, outcome) if p]
            base = "_".join(parts)
            path = folder / f"{base}.txt"
            # Avoid clobbering an existing file (same title within the same minute):
            # append seconds, then a counter, until the name is free.
            if path.exists():
                path = folder / f"{base}_{datetime.now().strftime('%S')}.txt"
                n = 1
                while path.exists():
                    path = folder / f"{base}_{datetime.now().strftime('%S')}_{n}.txt"
                    n += 1
            unc = entry.sizes
            header = [
                "PS5 Image Studio — build log",
                "=" * 48,
                f"Title:        {job.title or Path(job.src_path).name}",
                f"PPSA:         {job.ppsa or '—'}",
                f"Output path:  {job.final_path or '—'}",
                f"Format:       {(job.out_ext or '').lstrip('.') or '—'}",
                f"Source size:  {M.human_size(getattr(job, 'size_bytes', 0))}",
                f"Stored size:  {sizes}",
                f"Gain:         {gain}",
                f"Elapsed:      {M.fmt_secs(getattr(job, 'elapsed', 0))}",
                f"Result:       {outcome}",
                f"Timestamp:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 48,
                "",
            ]
            body = "\n".join(header) + "\n".join(job.log)
            path.write_text(body, encoding="utf-8")
            return str(path)
        except Exception as e:
            logging.warning("could not save build log: %s", e)
            return ""

    # ── misc ──────────────────────────────────────────────────
    def _refresh_data(self):
        self._refresh_meters()
        self._persist_queue()
        for key in ("dashboard", "queue", "history"):
            try:
                self.pages[key].refresh()
            except Exception:
                logging.exception("refresh failed for page %r", key)
        if self._current == "active":
            self.pages["active"].refresh()

    def _persist_queue(self):
        try:
            M.save_queue([j for j in self.appstate.jobs if j.status in ("waiting", "paused")])
        except Exception:
            pass

    def toast(self, msg):
        lbl = ctk.CTkLabel(self, text=msg, font=T.F["bodyb"], text_color=T.FG0, fg_color=T.BG4,
                           corner_radius=8, padx=18, pady=10)
        lbl.place(relx=0.5, rely=0.94, anchor="center")
        self.after(2200, lbl.destroy)

    # ── post-queue action (sleep / shutdown after a clean queue) ──
    def _on_queue_drained(self):
        """Called once when the queue empties. If the configured post-queue action
        is sleep/shutdown AND the batch finished strictly cleanly (>=1 done, no
        errors, no cancels), start a 60s cancellable countdown. Default 'nothing'
        does nothing. Fully guarded — never disrupts anything on failure."""
        try:
            action = getattr(self.appstate.settings, "post_queue_action", "nothing")
            if action not in ("sleep", "shutdown"):
                return
            summ = getattr(self.appstate, "batch_summary", {}) or {}
            done = summ.get("done", 0)
            errors = summ.get("error", 0)
            cancelled = summ.get("cancelled", 0)
            # Strict all-clean: at least one success, and nothing failed/cancelled.
            if not (done > 0 and errors == 0 and cancelled == 0):
                return
            self._start_post_queue_countdown(action)
        except Exception as e:
            logging.warning("post-queue action skipped: %s", e)

    def _start_post_queue_countdown(self, action: str, seconds: int = 60):
        # Don't stack countdowns.
        if self._pq_win is not None:
            return
        try:
            win = ctk.CTkToplevel(self)
        except Exception:
            return
        self._pq_win = win
        self._pq_remaining = seconds
        verb = "Shut down" if action == "shutdown" else "Sleep"
        win.title(f"{verb} after queue")
        win.geometry("460x220")
        win.configure(fg_color=T.BG1)
        try:
            win.transient(self)
        except Exception:
            pass
        # If the user closes the dialog with the window X, treat it as cancel.
        try:
            win.protocol("WM_DELETE_WINDOW", self._cancel_post_queue_countdown)
        except Exception:
            pass

        wrap = ctk.CTkFrame(win, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=22)
        ctk.CTkLabel(wrap, text=f"✅  Queue finished — {verb.lower()} scheduled",
                     font=T.F["title"], text_color=T.FG0, anchor="w").pack(anchor="w")
        ctk.CTkLabel(wrap, text="The build queue completed successfully with no "
                                "errors or cancellations.", font=T.F["meta"],
                     text_color=T.FG4, anchor="w", justify="left",
                     wraplength=400).pack(anchor="w", pady=(8, 12))
        self._pq_count_lbl = ctk.CTkLabel(
            wrap, text=self._pq_countdown_text(action, seconds),
            font=T.F["bodyb"], text_color=T.WARN_HI, anchor="w")
        self._pq_count_lbl.pack(anchor="w", pady=(0, 16))

        from .pages.base import ghost_btn, primary_btn
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(anchor="w")
        primary_btn(btns, "✕  Cancel", self._cancel_post_queue_countdown,
                    color=T.BG5, text_color=T.FG1).pack(side="left")

        # For shutdown, use the OS's own cancellable timer too (shutdown /s /t N),
        # so even if the app dies the user still has `shutdown /a`. Cancel calls
        # `shutdown /a`. Sleep has no cancellable native timer, so it only fires at
        # countdown expiry.
        if action == "shutdown":
            self._run_shutdown_command(seconds)

        self._pq_tick(action)

    def _pq_countdown_text(self, action: str, n: int) -> str:
        verb = "Shutting down" if action == "shutdown" else "Going to sleep"
        return f"{verb} in {n}s…  (Cancel to stay awake)"

    def _pq_tick(self, action: str):
        if self._pq_win is None:
            return
        self._pq_remaining -= 1
        if self._pq_remaining <= 0:
            # Time's up. Shutdown was already scheduled with the OS timer; sleep
            # fires now. Close the dialog either way.
            try:
                if action == "sleep":
                    self._run_sleep_command()
            finally:
                self._destroy_pq_win()
            return
        try:
            self._pq_count_lbl.configure(text=self._pq_countdown_text(action, self._pq_remaining))
        except Exception:
            pass
        self._pq_after = self.after(1000, lambda: self._pq_tick(action))

    def _cancel_post_queue_countdown(self):
        """Cancel a live countdown (Cancel button, window close, or a new build
        starting). Aborts the OS shutdown timer if one was scheduled."""
        if self._pq_win is None:
            return
        # Abort a pending OS shutdown (no-op if none / non-Windows).
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["shutdown", "/a"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        self._destroy_pq_win()
        try:
            self.toast("Post-queue action cancelled")
        except Exception:
            pass

    def _destroy_pq_win(self):
        if self._pq_after is not None:
            try:
                self.after_cancel(self._pq_after)
            except Exception:
                pass
            self._pq_after = None
        if self._pq_win is not None:
            try:
                self._pq_win.destroy()
            except Exception:
                pass
            self._pq_win = None

    def _run_shutdown_command(self, seconds: int):
        """Schedule a cancellable Windows shutdown. No-op (logged) elsewhere."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["shutdown", "/s", "/t", str(seconds)],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                logging.info("post-queue shutdown requested (no-op on this platform)")
        except Exception as e:
            logging.warning("shutdown command failed: %s", e)

    def _run_sleep_command(self):
        """Put the machine to sleep (Windows). No-op (logged) elsewhere."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                logging.info("post-queue sleep requested (no-op on this platform)")
        except Exception as e:
            logging.warning("sleep command failed: %s", e)

    def _show_completion_modal(self, job):
        """Modal shown once a build finishes successfully (job_done only).
        Reuses the existing explorer-open helper for Open Folder. Never fakes a
        compression figure — exFAT-only builds show 'No compression'."""
        from .pages.base import ghost_btn, primary_btn
        try:
            win = ctk.CTkToplevel(self)
        except Exception:
            return
        win.title("Build Finished")
        win.geometry("560x300")
        win.configure(fg_color=T.BG1)
        try:
            win.transient(self)
        except Exception:
            pass

        wrap = ctk.CTkFrame(win, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=22)

        ctk.CTkLabel(wrap, text="✅  Build Finished", font=T.F["title"],
                     text_color=T.SUCCESS_HI, anchor="w").pack(anchor="w")
        title = getattr(job, "display_name", "") or getattr(job, "title", "") or "Build"
        ctk.CTkLabel(wrap, text=f"{title} · {job.ppsa}", font=T.F["bodyb"],
                     text_color=T.FG1, anchor="w").pack(anchor="w", pady=(10, 2))

        # gain — only for compressed (ffpfsc) builds with a real value
        if getattr(job, "output_format", "ffpfsc") == "exfat":
            gain_txt = "No compression (exFAT image)"
        elif getattr(job, "gain", 0):
            gain_txt = f"{job.gain:.1f}% smaller than source"
        else:
            gain_txt = "No compression data"
        meta = f"Elapsed {M.fmt_secs(job.elapsed)}   ·   {gain_txt}"
        ctk.CTkLabel(wrap, text=meta, font=T.F["meta"], text_color=T.FG4,
                     anchor="w").pack(anchor="w", pady=(0, 12))

        out = getattr(job, "final_path", "") or ""
        if out:
            ctk.CTkLabel(wrap, text="Output", font=T.F["label"], text_color=T.FG5,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(wrap, text=out, font=T.F["monosm"], text_color=T.FG3,
                         anchor="w", wraplength=500, justify="left").pack(anchor="w", pady=(0, 4))

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(side="bottom", anchor="e", fill="x")
        primary_btn(btns, "✓  OK", win.destroy).pack(side="right")
        if out:
            def _open():
                from .pages.history import _open_in_explorer
                _open_in_explorer(out)
            ghost_btn(btns, "📂  Open Folder", _open, text_color=T.ACCENT_HI)\
                .pack(side="right", padx=(0, 10))

        try:
            win.after(60, win.lift)
        except Exception:
            pass

    def _on_close(self):
        # Show a small farewell dialog with a Ko-fi link. Guarded: if the dialog
        # can't be built for any reason, fall straight through to closing so the
        # app can always exit. Don't interrupt an active build with extra friction
        # beyond this single optional dialog.
        try:
            if getattr(self, "_closing", False):
                return
            self._closing = True
            self._show_close_dialog()
        except Exception:
            self._do_close()

    def _show_close_dialog(self):
        try:
            win = ctk.CTkToplevel(self)
        except Exception:
            self._do_close()
            return
        self._close_win = win
        win.title("Thanks for using PS5 Image Studio")
        win.geometry("460x280")
        win.configure(fg_color=T.BG1)
        try:
            win.transient(self)
            win.grab_set()
        except Exception:
            pass
        # Closing this dialog with the window X == just close the app.
        try:
            win.protocol("WM_DELETE_WINDOW", self._do_close)
        except Exception:
            pass

        wrap = ctk.CTkFrame(win, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=22)
        ctk.CTkLabel(wrap, text="👋  Thanks for using PS5 Image Studio",
                     font=T.F["title"], text_color=T.FG0, anchor="w").pack(anchor="w")
        ctk.CTkLabel(wrap, text=("This is a free community tool. If it saved you "
                                 "time, a coffee helps keep it going — totally "
                                 "optional."), font=T.F["meta"], text_color=T.FG4,
                     anchor="w", justify="left", wraplength=410).pack(anchor="w",
                                                                      pady=(8, 12))
        # Backend credit — PS5 Image Studio is a front-end over Nazky's LazyMkPFS.
        credit = ctk.CTkFrame(wrap, fg_color="transparent")
        credit.pack(anchor="w", pady=(0, 16))
        ctk.CTkLabel(credit, text="Powered by Nazky's LazyMkPFS backend —",
                     font=T.F["meta"], text_color=T.FG5, anchor="w")\
            .pack(side="left")
        nz = ctk.CTkLabel(credit, text="github.com/Nazky", font=T.F["meta"],
                          text_color=T.ACCENT_HI, anchor="w", cursor="hand2")
        nz.pack(side="left", padx=(4, 0))
        nz.bind("<Button-1>", lambda _e: self._open_nazky())
        nz.bind("<Enter>", lambda _e: nz.configure(text_color=T.ACCENT))
        nz.bind("<Leave>", lambda _e: nz.configure(text_color=T.ACCENT_HI))

        from .pages.base import primary_btn
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(anchor="w")
        primary_btn(btns, "☕  Support on Ko-fi", self._open_kofi,
                    color=T.ACCENT, text_color=T.BG0).pack(side="left")
        primary_btn(btns, "Close", self._do_close,
                    color=T.BG5, text_color=T.FG1).pack(side="left", padx=(10, 0))

    def _open_kofi(self):
        import webbrowser
        try:
            webbrowser.open("https://ko-fi.com/deckerr9746220")
        except Exception:
            pass
        # Opening Ko-fi doesn't close the app — let them read the page, then they
        # can hit Close (or the window X) to exit.

    def _open_nazky(self):
        import webbrowser
        try:
            webbrowser.open("https://github.com/Nazky")
        except Exception:
            pass

    def _do_close(self):
        try:
            if getattr(self, "_close_win", None) is not None:
                self._close_win.destroy()
                self._close_win = None
        except Exception:
            pass
        try:
            self.worker.shutdown()
        except Exception:
            pass
        self.destroy()


def main():
    import os
    import sys
    demo = ("--demo" in sys.argv) or (os.environ.get("LAZY_STUDIO_DEMO") == "1")
    App(demo=demo).mainloop()


if __name__ == "__main__":
    main()
