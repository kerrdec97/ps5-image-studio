"""Active Build: live progress, phase dots, stats, and the Build Log."""
from __future__ import annotations
import customtkinter as ctk
from .. import theme as T
from .. import models as M
from ..widgets import Card, StatTile, StepDots, LogView
from .base import Page, primary_btn, ghost_btn, home_btn_large


class ActiveBuildPage(Page):
    def build(self):
        self.jid = None
        self._indet = False   # is the progress bar currently in indeterminate scan mode?
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 2))
        home_btn_large(head, self.app).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ctk.CTkLabel(head, text="Active Build", font=T.F["h1"], text_color=T.FG0).grid(row=1, column=0)
        self.badge = ctk.CTkLabel(head, text="⚡ BUILDING", font=T.F["meta"], text_color=T.WARN_HI,
                                  fg_color=T.WARN_BG, corner_radius=999, padx=11, pady=3)
        self.badge.grid(row=1, column=1, padx=10)
        self.subtitle = ctk.CTkLabel(self, text="", font=T.F["body"], text_color=T.FG5, anchor="w")
        self.subtitle.grid(row=1, column=0, sticky="w", padx=30, pady=(0, 18))

        # progress + dots
        pc = Card(self)
        pc.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 16))
        pc.grid_columnconfigure(0, weight=1)
        prow = ctk.CTkFrame(pc, fg_color="transparent")
        prow.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 7))
        prow.grid_columnconfigure(0, weight=1)
        self.phase_lbl = ctk.CTkLabel(prow, text="Waiting…", font=T.F["body"], text_color=T.FG3, anchor="w")
        self.phase_lbl.grid(row=0, column=0, sticky="w")
        self.pct_lbl = ctk.CTkLabel(prow, text="0%", font=T.F["monob"], text_color=T.ACCENT)
        self.pct_lbl.grid(row=0, column=1, sticky="e")
        self.bar = ctk.CTkProgressBar(pc, height=16, corner_radius=5, progress_color=T.ACCENT, fg_color=T.BG5)
        self.bar.grid(row=1, column=0, sticky="ew", padx=24)
        sep = ctk.CTkFrame(pc, fg_color=T.BORDER1, height=1)
        sep.grid(row=2, column=0, sticky="ew", padx=24, pady=(18, 0))
        self.dots = StepDots(pc, ["Scan", "Compress", "Verify", "Move"])
        self.dots.grid(row=3, column=0, sticky="ew", padx=24, pady=(16, 18))

        # stat tiles
        tiles = ctk.CTkFrame(self, fg_color="transparent")
        tiles.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 16))
        for i in range(6):
            tiles.grid_columnconfigure(i, weight=1, uniform="s")
        self.tile_speed = StatTile(tiles, "Speed", "—", "", T.ACCENT)
        self.tile_prog = StatTile(tiles, "Progress", "0%", "")
        self.tile_eta = StatTile(tiles, "ETA", "—", "")
        self.tile_elapsed = StatTile(tiles, "Elapsed", "0s", "")
        self.tile_phase = StatTile(tiles, "Phase", "—", "")
        self.tile_gain = StatTile(tiles, "Gain", "—", "", T.SUCCESS)
        for i, t in enumerate((self.tile_speed, self.tile_prog, self.tile_eta,
                               self.tile_elapsed, self.tile_phase, self.tile_gain)):
            t.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))

        # build log
        logc = Card(self)
        logc.grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 16))
        logc.grid_columnconfigure(0, weight=1)
        lhdr = ctk.CTkFrame(logc, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        lhdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lhdr, text="📋  BUILD LOG", font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=12, pady=8)
        # Current Action — live, finer-grained than PHASE (Mounting/Formatting/…)
        self.action_lbl = ctk.CTkLabel(lhdr, text="", font=T.F["bodyb"],
                                       text_color=T.ACCENT_HI, anchor="e")
        self.action_lbl.grid(row=0, column=1, sticky="e", padx=12, pady=8)
        # Optional one-line explanatory hint (e.g. what OSFMount is doing).
        self.hint_lbl = ctk.CTkLabel(logc, text="", font=T.F["meta"], text_color=T.FG5,
                                     anchor="w", justify="left", wraplength=900)
        self.hint_lbl.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 2))
        self.log = LogView(logc, height=200)
        self.log.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))

        # controls
        self._btns = ctk.CTkFrame(self, fg_color="transparent")
        self._btns.grid(row=5, column=0, sticky="ew", padx=30, pady=(0, 30))
        self._btns.grid_columnconfigure(2, weight=1)
        # The build widgets that should be HIDDEN when truly idle (empty progress
        # bar / stage dots / stat tiles / log look broken with nothing running).
        self._build_widgets = [pc, tiles, logc, self._btns]
        # Idle panel (built once, shown only in true idle). Replaces the empty
        # build view with a useful "no build running" workstation panel.
        self._idle = ctk.CTkFrame(self, fg_color="transparent")
        self._idle.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 16))
        self._idle.grid_columnconfigure(0, weight=1)
        self._idle.grid_remove()
        # build-control buttons (shown while a build is running / idle)
        self.pause_btn = ghost_btn(self._btns, "⏸  Pause queue", self._pause, text_color=T.WARN_HI)
        self.stop_btn = ghost_btn(self._btns, "⏹  Stop build", self.app.stop_current,
                                  text_color=T.DANGER_HI)
        self.back_btn = ghost_btn(self._btns, "☰  Back to Queue",
                                  lambda: self.app.show_page("queue"))
        # completion buttons (shown after a terminal event)
        self.open_btn = ghost_btn(self._btns, "📂  Open Folder", self._open_output,
                                  text_color=T.ACCENT_HI)
        self.ok_btn = ghost_btn(self._btns, "✓  OK", self._ack_complete)
        self._show_build_controls()

    def _show_build_view(self):
        """Restore the live-build widgets (progress/dots/tiles/log) and hide the
        idle panel. Used whenever there's a running job or a summary to show."""
        self._idle.grid_remove()
        for w in self._build_widgets:
            w.grid()

    def _render_idle(self):
        """True-idle workstation panel: no build running. Shows queue state and
        the right next action, instead of an empty progress bar / log that looks
        like something failed."""
        self._set_indeterminate(False)
        idle = T.status_style("idle")
        self.badge.configure(text="IDLE", text_color=idle["text"], fg_color=idle["bg"])
        self.subtitle.configure(text="No build is currently running.")
        # Hide the empty build widgets; show the idle panel.
        for w in self._build_widgets:
            w.grid_remove()
        self._idle.grid()
        for w in self._idle.winfo_children():
            w.destroy()

        waiting = self.state.waiting()
        card = Card(self._idle)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=28, pady=26)
        inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(inner, text="⏸  No build running", font=T.F["h2"], text_color=T.FG0,
                     anchor="w").grid(row=0, column=0, sticky="w")

        if not waiting:
            # Empty queue.
            ctk.CTkLabel(inner, text="No jobs are currently queued.", font=T.F["body"],
                         text_color=T.FG4, anchor="w").grid(row=1, column=0, sticky="w", pady=(6, 18))
            btns = ctk.CTkFrame(inner, fg_color="transparent")
            btns.grid(row=2, column=0, sticky="w")
            primary_btn(btns, "⚡  New Build", lambda: self.app.enter_mode("build"))\
                .grid(row=0, column=0, padx=(0, 8))
            ghost_btn(btns, "▤  Queue", lambda: self.app.show_page("queue"))\
                .grid(row=0, column=1)
            return

        # One or more jobs waiting.
        total = sum(j.size_bytes for j in waiting)
        n = len(waiting)
        summary = (f"{n} build waiting" if n == 1 else
                   f"{n} builds waiting · {M.human_size(total)} total")
        ctk.CTkLabel(inner, text=summary, font=T.F["body"], text_color=T.ACCENT_HI, anchor="w")\
            .grid(row=1, column=0, sticky="w", pady=(6, 14))

        # Next job card.
        nxt = waiting[0]
        njob = ctk.CTkFrame(inner, fg_color=T.BG3, corner_radius=8)
        njob.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        njob.grid_columnconfigure(0, weight=1)
        label = "Next:" if n > 1 else "Queued:"
        ctk.CTkLabel(njob, text=label, font=T.F["meta"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(njob, text=nxt.display_name, font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=16)
        fmt = "exFAT image" if getattr(nxt, "output_format", "ffpfsc") == "exfat" else "FFPFSC"
        ctk.CTkLabel(njob, text=f"{nxt.ppsa or '—'} · {fmt} · {M.human_size(nxt.size_bytes)}",
                     font=T.F["monosm"], text_color=T.FG5, anchor="w")\
            .grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="w")
        primary_btn(btns, "▶  Start Queue", self._start_from_idle)\
            .grid(row=0, column=0, padx=(0, 8))
        ghost_btn(btns, "▤  View Queue", lambda: self.app.show_page("queue"))\
            .grid(row=0, column=1)

    def _start_from_idle(self):
        self.app.start_queue()

    def _show_build_controls(self):
        for b in (self.open_btn, self.ok_btn):
            b.grid_remove()
        self.pause_btn.grid(row=0, column=0, padx=(0, 10))
        self.stop_btn.grid(row=0, column=1)
        self.back_btn.grid(row=0, column=2, sticky="e")

    def _show_completion_controls(self):
        for b in (self.pause_btn, self.stop_btn, self.back_btn):
            b.grid_remove()
        self.open_btn.grid(row=0, column=0, padx=(0, 10))
        self.ok_btn.grid(row=0, column=1)

    def _open_output(self):
        from .history import _open_in_explorer
        last = getattr(self.state, "last_finished", None)
        path = getattr(last, "final_path", "") if last else ""
        if path:
            _open_in_explorer(path)

    def _ack_complete(self):
        # Acknowledge completion: unbind from the finished job and restore build
        # controls, falling back to the retained last-build summary (build controls)
        # or true IDLE. Clearing self.jid prevents refresh from re-detecting the
        # still-in-list terminal job and re-showing the completion buttons.
        self.jid = None
        if getattr(self.state, "last_finished", None) is not None and self.state.running() is None:
            self._show_build_view()
            self._render_summary(self.state.last_finished)
            self._show_build_controls()
        else:
            self._render_idle()

    # ── live updates ──────────────────────────────────────────
    def on_show(self):
        self.refresh()

    def refresh(self):
        job = self.state.running() or self.state.job(self.jid)
        # A job still in the list but already in a terminal state should render as
        # a completion summary, not the live view — otherwise the post-job_done
        # _refresh_data() would clobber the DONE badge / "Completed" ETA / buttons.
        if job is not None and getattr(job, "status", "") in ("done", "error", "cancelled"):
            self._show_build_view()
            self._render_summary(job)
            self._show_completion_controls()
            return
        if not job:
            # No running job: fall back to the last terminal summary (this session)
            # instead of a blank IDLE screen. True IDLE only when nothing has run.
            last = getattr(self.state, "last_finished", None)
            if last is not None:
                self._show_build_view()
                self._render_summary(last)
                self._show_build_controls()
            else:
                self._render_idle()
            return
        self.jid = job.id
        self._show_build_view()
        self._show_build_controls()
        style = T.status_style(job.status)
        badge_text = "⚡ BUILDING" if job.status == "running" else style["label"]
        self.badge.configure(text=badge_text, text_color=style["text"], fg_color=style["bg"])
        self.subtitle.configure(text=f"{job.display_name} · {job.ppsa} · {M.human_size(job.size_bytes)}")
        steps = getattr(job, "_steps", None) or ["Scan", "Compress", "Verify", "Move"]
        self.dots.build(steps)
        self.dots.set_active(job.phase_idx)
        self.log.clear()
        for ln in job.log[-400:]:
            self.log.add(ln)
        self.update_progress(job)

    def _render_summary(self, job):
        """Paint a static summary of the last finished/failed/cancelled job.
        Reads only what the job actually holds — never fabricates missing values."""
        self._set_indeterminate(False)
        outcome = getattr(job, "status", "done") or "done"
        style = T.status_style(outcome)
        icon = {"done": "✅ DONE", "error": "❌ FAILED", "cancelled": "⏹ CANCELLED"}.get(
            outcome, style["label"])
        self.badge.configure(text=icon, text_color=style["text"], fg_color=style["bg"])

        # subtitle: title · ppsa · files · output path (only the parts we have)
        bits = [job.display_name, job.ppsa]
        fc = getattr(job, "file_count", 0) or 0
        if outcome == "done" and fc:
            bits.append(f"{fc:,} files")
        out = getattr(job, "final_path", "") or ""
        if out:
            bits.append(out)
        self.subtitle.configure(text=" · ".join(b for b in bits if b))

        steps = getattr(job, "_steps", None) or ["Scan", "Compress", "Verify", "Move"]
        self.dots.build(steps)
        if outcome == "done":
            self.dots.set_done()
            self.bar.set(1.0)
            self.pct_lbl.configure(text="100%")
        else:
            # leave dots/progress at the point reached; don't fake completion
            self.dots.set_active(getattr(job, "phase_idx", 0))
            self.bar.set(getattr(job, "progress", 0.0) or 0.0)
            self.pct_lbl.configure(text=f"{int((getattr(job, 'progress', 0.0) or 0.0) * 100)}%")

        self.phase_lbl.configure(text={"done": "Completed", "error": "Failed",
                                       "cancelled": "Cancelled"}.get(outcome, "Finished"))
        self.action_lbl.configure(text="▸ Completed" if outcome == "done" else "")
        # tiles: only fill what's known
        self.tile_speed.set("—")
        self.tile_eta.set("Completed" if outcome == "done" else "—")
        self.tile_prog.set(self.pct_lbl.cget("text"))
        self.tile_elapsed.set(M.fmt_secs(job.elapsed) if getattr(job, "elapsed", 0) else "—")
        self.tile_phase.set(getattr(job, "phase", "") or self.phase_lbl.cget("text"))
        self.tile_gain.set(f"{job.gain:.1f}%" if outcome == "done" and getattr(job, "gain", 0) else "—")

        self.log.clear()
        tail = getattr(job, "log", None) or []
        if tail:
            for ln in tail[-400:]:
                self.log.add(ln)

    def set_steps(self, job, steps):
        # Called by the app at job_start with the live job — bind to it here so
        # every gated live handler below recognises this job (mirrors Queue's rebind).
        self.jid = job.id
        job._steps = steps
        self.dots.build(steps)
        self._show_build_controls()
        self.action_lbl.configure(text="")
        # Reset the live display to its initial state so a new build never inherits
        # the PREVIOUS build's values. In particular Gain is only refreshed at
        # completion, so without this it would keep showing the last build's gain
        # (e.g. "63.6%") all through this build's Scan/Create-exFAT phases. The
        # other tiles self-correct on the first progress/phase event, but resetting
        # them too removes the brief stale window between job_start and that event.
        # Stop any indeterminate scan animation FIRST so the bar returns to
        # determinate before we set it to 0; the upcoming scan 'phase' event will
        # re-enable indeterminate via set_phase()->update_progress() if appropriate.
        self._set_indeterminate(False)
        self.bar.set(0.0)
        self.pct_lbl.configure(text="0%")
        self.phase_lbl.configure(text="Waiting…")
        self.tile_speed.set("—")
        self.tile_prog.set("0%")
        self.tile_eta.set("—")
        self.tile_elapsed.set("0s")
        self.tile_phase.set("—")
        self.tile_gain.set("—")

    def set_action(self, job, text):
        # Live 'current action' indicator (finer than PHASE). Gated on jid like
        # the other live handlers so a stale job can't update the tile.
        if self.jid != job.id:
            return
        self.action_lbl.configure(text=("▸ " + text) if text else "")
        # Explain the OSFMount step the first time mounting/formatting is shown, so
        # the disk-mount activity (and any UAC/driver prompt) isn't mysterious.
        low = (text or "").lower()
        if ("mount" in low or "format" in low) and hasattr(self, "hint_lbl"):
            self.hint_lbl.configure(
                text="ℹ Using OSFMount to mount a temporary disk image — this is "
                     "part of building the exFAT image and needs admin rights.")
        elif hasattr(self, "hint_lbl") and not text:
            self.hint_lbl.configure(text="")

    def set_phase(self, job):
        if self.jid is None:
            self.jid = job.id
        if self.jid == job.id:
            self.dots.set_active(job.phase_idx)
            self.tile_phase.set(job.phase or "—")
            # Entering a scan-like phase arrives as a 'phase' event (no 'progress'
            # event fires during the walk), so drive the indeterminate bar from here
            # as well. Routing through update_progress keeps the label/tiles
            # consistent and flips back to determinate the moment real progress lands.
            self.update_progress(job)

    def add_log(self, job, line):
        if self.jid is None:
            self.jid = job.id
        if self.jid == job.id:
            self.log.add(line)

    @staticmethod
    def _is_scan_like_phase(phase: str) -> bool:
        """Phases whose underlying work (the dump-tree os.walk inside
        calculate_exfat_size) emits NO progress telemetry, so a real percentage
        can't be shown. These are the phases that otherwise sit at a dead 0%."""
        p = (phase or "").lower()
        return "scan" in p or "create exfat" in p or "exfat" in p

    def _wants_indeterminate(self, job) -> bool:
        """True when we should animate an indeterminate bar instead of showing a
        dead 0%. Condition: a scan-like phase with no real progress yet (no
        percentage and no speed emitted). As soon as the child emits a real
        progress line (pct>0 or a speed), this turns False and the normal
        determinate bar takes over. We never fabricate counts — only convey motion.
        """
        prog = getattr(job, "progress", 0.0) or 0.0
        speed = (getattr(job, "speed", "") or "").strip()
        status = getattr(job, "status", "") or ""
        if status in ("done", "error", "cancelled"):
            return False
        return self._is_scan_like_phase(getattr(job, "phase", "")) and prog <= 0.0 and not speed

    def _set_indeterminate(self, on: bool):
        """Toggle the progress bar between indeterminate animation and the normal
        determinate mode. Idempotent so repeated progress/phase events don't
        restart the animation each tick."""
        if on == self._indet:
            return
        self._indet = on
        try:
            if on:
                self.bar.configure(mode="indeterminate")
                self.bar.start()
            else:
                self.bar.stop()
                self.bar.configure(mode="determinate")
        except Exception:
            # If the CTk version lacks indeterminate mode, fall back silently to a
            # static bar — the prominent "Scanning…" label + live Elapsed still
            # convey that work is ongoing.
            self._indet = False

    def update_progress(self, job):
        if self.jid is None:
            self.jid = job.id
        if self.jid != job.id:
            return
        nsteps = len(getattr(self.dots, "dots", []) or [])
        cur = getattr(job, "phase_idx", 0) + 1
        phase_pos = f"Phase {cur} of {nsteps}" if nsteps else ""

        # Indeterminate scan state: a scan-like phase with no real telemetry yet.
        # Animate the bar, show a clear "Scanning…" message and a "—" percent
        # instead of a dead 0% that reads as frozen. Elapsed keeps ticking via the
        # app pump, so the user sees both motion and a climbing timer. No counts
        # are fabricated.
        if self._wants_indeterminate(job):
            self._set_indeterminate(True)
            phase = job.phase or "Scanning"
            msg = "Scanning source — large titles can take several minutes to analyse"
            self.phase_lbl.configure(
                text=f"{phase}: {msg}   ·   {phase_pos}" if phase_pos else f"{phase}: {msg}")
            self.pct_lbl.configure(text="—")
            self.tile_speed.set("—")
            self.tile_prog.set("scanning…")
            self.tile_eta.set("—")
            self.tile_elapsed.set(M.fmt_secs(job.elapsed))
            self.tile_phase.set(f"{job.phase or '—'} ({cur}/{nsteps})" if nsteps else (job.phase or "—"))
            return

        # Normal determinate progress.
        self._set_indeterminate(False)
        pct = int(job.progress * 100)
        self.bar.set(job.progress)
        self.pct_lbl.configure(text=f"{pct}%")
        # Only show the compression backend during the compression phase — it's
        # irrelevant (and misleading) during scan / exFAT creation / move.
        phase = job.phase or "Working"
        # Explicit "Phase X of Y" using the emitted phase index (idx/total are
        # phase counts, not file counts — honest progress structure).
        if self._is_compress_phase(phase):
            base = f"{phase} · {M.BACKEND_LABELS[job.backend]} L{job.level}"
        else:
            base = phase
        self.phase_lbl.configure(text=f"{base}   ·   {phase_pos}" if phase_pos else base)
        self.tile_speed.set(job.speed or "—")
        self.tile_prog.set(f"{pct}%")
        self.tile_eta.set(job.eta or "—")
        self.tile_elapsed.set(M.fmt_secs(job.elapsed))
        self.tile_phase.set(f"{job.phase or '—'} ({cur}/{nsteps})" if nsteps else (job.phase or "—"))
        if job.status == "done":
            self.tile_gain.set(f"{job.gain:.1f}%")

    @staticmethod
    def _is_compress_phase(phase: str) -> bool:
        p = (phase or "").lower()
        return "compress" in p or "pfs" in p

    def on_done(self, job):
        if self.jid is None:
            self.jid = job.id
        if self.jid != job.id:
            return
        self._set_indeterminate(False)
        self.badge.configure(text="✅ DONE", text_color=T.SUCCESS_HI, fg_color=T.SUCCESS_BG)
        self.dots.set_done()
        self.bar.set(1.0)
        self.pct_lbl.configure(text="100%")
        self.tile_gain.set(f"{job.gain:.1f}%" if getattr(job, "gain", 0) else "—")
        self.tile_elapsed.set(M.fmt_secs(job.elapsed))
        self.tile_eta.set("Completed")
        self.tile_speed.set("—")
        # Surface final total file count alongside the existing summary line.
        fc = getattr(job, "file_count", 0) or 0
        bits = [job.display_name, job.ppsa]
        if fc:
            bits.append(f"{fc:,} files")
        out = getattr(job, "final_path", "") or ""
        if out:
            bits.append(out)
        self.subtitle.configure(text=" · ".join(b for b in bits if b))
        self.phase_lbl.configure(text="Completed")
        self.action_lbl.configure(text="▸ Completed")
        self._show_completion_controls()

    def _pause(self):
        self.app.toggle_pause()
        self.pause_btn.configure(text="▶  Resume queue" if self.app.worker.is_paused() else "⏸  Pause queue")
