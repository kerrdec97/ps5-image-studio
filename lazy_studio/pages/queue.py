"""Queue: running job (live) + waiting jobs, with queue-level controls."""
from __future__ import annotations
import json
from tkinter import filedialog
import customtkinter as ctk
from .. import theme as T
from .. import models as M
from .base import Page, primary_btn, ghost_btn, home_btn_large


class QueuePage(Page):
    def build(self):
        self.running_refs = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 16))
        head.grid_columnconfigure(0, weight=1)
        home_btn_large(head, self.app).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ctk.CTkLabel(head, text="Queue", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w")
        self.sub = ctk.CTkLabel(head, text="", font=T.F["body"], text_color=T.FG5, anchor="w")
        self.sub.grid(row=2, column=0, sticky="w", pady=(2, 0))

        tb = ctk.CTkFrame(head, fg_color="transparent")
        tb.grid(row=1, column=1, rowspan=2, sticky="e")
        self.start_btn = primary_btn(tb, "▶  Start All", self._start, height=34)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))
        self.pause_btn = ghost_btn(tb, "⏸  Pause", self._toggle_pause, height=34)
        self.pause_btn.grid(row=0, column=1, padx=(0, 8))
        ghost_btn(tb, "💾  Save Queue", self._save_queue, height=34).grid(row=0, column=2, padx=(0, 8))
        # "Add" routes to the modern Build Wizard (the primary build flow), matching
        # every other "New Build" entry point (Home, Overview, Active Build, History).
        # The legacy AddJobPage has been removed entirely.
        ghost_btn(tb, "✚  Add", lambda: self.app.enter_mode("build"), height=34).grid(row=0, column=3)
        if getattr(self.app, "demo", False):
            ghost_btn(tb, "🧪  Add demo job", self.app.add_demo_job, height=34,
                      text_color=T.SUCCESS_HI).grid(row=0, column=4, padx=(8, 0))

        # Summary strip (compact KPI tiles) above the cards — populated in refresh.
        self.summary_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_holder.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 12))
        self.summary_holder.grid_columnconfigure(0, weight=1)

        self.list = ctk.CTkFrame(self, fg_color="transparent")
        self.list.grid(row=2, column=0, sticky="ew", padx=30)
        self.list.grid_columnconfigure(0, weight=1)

        self.tip = ctk.CTkLabel(
            self, text="💡 Tip — Leave the queue running overnight; completed images move to the "
                       "archive automatically. For 100–300 GB images keep Concurrent jobs = 1.",
            font=T.F["label"], text_color=T.SUCCESS_HI, fg_color=T.SUCCESS_BG, corner_radius=6,
            anchor="w", justify="left", wraplength=900, padx=16, pady=11)
        self.tip.grid(row=3, column=0, sticky="ew", padx=30, pady=16)

    def _build_summary(self, jobs):
        for w in self.summary_holder.winfo_children():
            w.destroy()
        # Hidden when there's nothing to summarize (empty queue shows its own message).
        if not jobs:
            return

        queued = sum(1 for j in jobs if j.status == "waiting")
        paused = sum(1 for j in jobs if j.status == "paused")
        running = next((j for j in jobs if j.status == "running"), None)
        waiting_jobs = [j for j in jobs if j.status == "waiting"]
        waiting_bytes = sum(j.size_bytes for j in waiting_jobs)
        nxt = waiting_jobs[0] if waiting_jobs else None

        if running is not None:
            batch_text, batch_color = "Running", T.WARN_HI
        elif self.app.worker.is_paused():
            batch_text, batch_color = "Paused", T.FG4
        else:
            batch_text, batch_color = "Idle", T.FG4

        next_name = "—"
        if nxt is not None:
            nm = nxt.display_name
            next_name = nm if len(nm) <= 20 else nm[:19] + "…"

        # Compact KPI labels with units on the count tiles (e.g. "1 job", "12.4 GB").
        # Presentational only — values come from the already-computed locals above.
        queued_txt = f"{queued} job" if queued == 1 else f"{queued} jobs"
        paused_txt = f"{paused} job" if paused == 1 else f"{paused} jobs"
        tiles = [
            ("📦", "Queued", queued_txt, T.FG1),
            ("💾", "Waiting", M.human_size(waiting_bytes), T.ACCENT_HI),
            ("⏭", "Next", next_name, T.FG2),
            ("⏸", "Paused", paused_txt, T.WARN_HI if paused else T.FG4),
            ("⚙", "Status", batch_text, batch_color),
        ]
        strip = ctk.CTkFrame(self.summary_holder, fg_color="transparent")
        strip.grid(row=0, column=0, sticky="ew")
        for i in range(len(tiles)):
            strip.grid_columnconfigure(i, weight=1, uniform="qsum")
        for i, (icon, label, value, color) in enumerate(tiles):
            t = ctk.CTkFrame(strip, fg_color=T.BG3, corner_radius=7)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            t.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(t, text=f"{icon}  {label}", font=T.F["meta"], text_color=T.FG5,
                         anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(t, text=value, font=T.F["monob"], text_color=color, anchor="w")\
                .grid(row=1, column=0, sticky="w", padx=12, pady=(2, 11))

    def refresh(self):
        self.running_refs = None
        for w in self.list.winfo_children():
            w.destroy()
        st = self.state
        jobs = [j for j in st.jobs if j.status in ("running", "waiting", "paused")]
        total_bytes = sum(j.size_bytes for j in jobs)
        self.sub.configure(text=f"{len(jobs)} jobs · {M.human_size(total_bytes)} in")
        self.pause_btn.configure(text="▶  Resume" if self.app.worker.is_paused() else "⏸  Pause")
        self._build_summary(jobs)

        # Cards are self-describing (labeled fields), so no table header row.
        if not jobs:
            summary = getattr(self.state, "batch_summary", None)
            if summary:
                self._render_batch_summary(summary)
            else:
                ctk.CTkLabel(self.list, text="Queue is empty. Add a build job to begin.",
                             font=T.F["body"], text_color=T.FG5).grid(row=1, column=0, pady=30)
            return

        r = 0
        for j in jobs:
            self._row(j, r)
            r += 1

    def _render_batch_summary(self, s):
        """Completion card shown when a batch has drained. Green if all-success,
        warning-toned if any failed; cancelled counted separately. No faked data."""
        done = s.get("done", 0)
        failed = s.get("error", 0)
        cancelled = s.get("cancelled", 0)
        avg_gain = s.get("avg_gain")
        all_ok = failed == 0 and cancelled == 0 and done > 0
        if all_ok:
            icon, fg, bg = "✅", T.SUCCESS_HI, T.SUCCESS_BG
            head = f"Batch complete — {done} build{'s' if done != 1 else ''} succeeded"
        elif failed:
            icon, fg, bg = "⚠️", T.WARN_HI, T.WARN_BG
            head = f"Batch finished with {failed} failure{'s' if failed != 1 else ''}"
        else:
            icon, fg, bg = "⏹", T.FG3, T.BG4
            head = "Batch finished"

        card = ctk.CTkFrame(self.list, fg_color=bg, corner_radius=8)
        card.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=f"{icon}  {head}", font=T.F["bodyb"], text_color=fg,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))

        parts = [f"{done} completed"]
        if failed:
            parts.append(f"{failed} failed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")
        if avg_gain is not None:
            parts.append(f"avg {avg_gain:.1f}% gain")
        ctk.CTkLabel(card, text=" · ".join(parts), font=T.F["monosm"], text_color=T.FG3,
                     anchor="w").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))
        ghost_btn(card, "🕓  View History", lambda: self.app.show_page("history"), height=30)\
            .grid(row=0, column=1, rowspan=2, sticky="e", padx=18)

    def _row(self, j, r):
        running = j.status == "running"
        card = ctk.CTkFrame(self.list, fg_color=T.BG3,
                            border_color=T.ACCENT if running else T.BORDER2, border_width=1,
                            corner_radius=8)
        card.grid(row=r, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        style = T.status_style(j.status)

        # Header: status dot + name + status pill (left), actions (right).
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        top.grid_columnconfigure(1, weight=1)
        dot = ctk.CTkFrame(top, width=10, height=10, corner_radius=5, fg_color=style["fg"])
        dot.grid(row=0, column=0, padx=(0, 10))
        dot.grid_propagate(False)
        titlerow = ctk.CTkFrame(top, fg_color="transparent")
        titlerow.grid(row=0, column=1, sticky="w")
        # Long game titles wrap cleanly within the available width instead of
        # pushing the status pill/actions off the card.
        ctk.CTkLabel(titlerow, text=j.display_name, font=T.F["h2"], text_color=T.FG0,
                     anchor="w", justify="left", wraplength=560)\
            .grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titlerow, text=style["label"], font=T.F["meta"], text_color=style["text"],
                     fg_color=style["bg"], corner_radius=999, padx=9, pady=2)\
            .grid(row=0, column=1, sticky="w", padx=(10, 0))
        # Per-job actions (top-right).
        act = ctk.CTkFrame(top, fg_color="transparent")
        act.grid(row=0, column=2, sticky="e")
        if running:
            ctk.CTkButton(act, text="⏹  Stop", width=88, height=30, fg_color=T.BG5,
                          hover_color="#2a0a0a", text_color=T.DANGER_HI, font=T.F["meta"],
                          command=self.app.stop_current).grid(row=0, column=0)
        else:
            ctk.CTkButton(act, text="▲  Move Up", width=88, height=30, fg_color=T.BG5,
                          hover_color=T.BORDER3, text_color=T.FG3, font=T.F["meta"],
                          command=lambda: self._move_up(j)).grid(row=0, column=0, padx=(0, 6))
            ctk.CTkButton(act, text="✕  Remove", width=88, height=30, fg_color=T.BG5,
                          hover_color="#2a0a0a", text_color=T.FG3, font=T.F["meta"],
                          command=lambda: self.app.remove_job(j.id)).grid(row=0, column=1)

        # Field grid: PPSA · type, Format, Size, Destination — labeled, stacked.
        fmt = "exFAT image" if getattr(j, "output_format", "ffpfsc") == "exfat" else "FFPFSC"
        fields = ctk.CTkFrame(card, fg_color="transparent")
        fields.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14 if not running else 8))
        for c in range(4):
            fields.grid_columnconfigure(c, weight=1, uniform="qf")
        cells = [
            ("PPSA", f"{j.ppsa or '—'}"),
            ("FORMAT", fmt),
            ("SIZE", M.human_size(j.size_bytes)),
            ("PIPELINE", j.pipeline_short()),
        ]
        for c, (label, value) in enumerate(cells):
            cell = ctk.CTkFrame(fields, fg_color="transparent")
            cell.grid(row=0, column=c, sticky="w")
            ctk.CTkLabel(cell, text=label, font=T.F["meta"], text_color=T.FG6, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            vcolor = T.ACCENT_HI if (label == "PIPELINE" and running) else T.FG2
            ctk.CTkLabel(cell, text=value, font=T.F["monosm"], text_color=vcolor, anchor="w")\
                .grid(row=1, column=0, sticky="w", pady=(1, 0))
        # Destination on its own line (paths are long).
        drow = ctk.CTkFrame(card, fg_color="transparent")
        drow.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14 if not running else 8))
        drow.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(drow, text="DESTINATION", font=T.F["meta"], text_color=T.FG6, anchor="w")\
            .grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(drow, text=str(j.final_dir()), font=T.F["monosm"], text_color=T.FG4,
                     anchor="w", wraplength=720, justify="left")\
            .grid(row=1, column=0, sticky="w", pady=(1, 0))

        # Live progress (running job only) — keeps the running_refs contract intact.
        if running:
            prow = ctk.CTkFrame(card, fg_color="transparent")
            prow.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
            prow.grid_columnconfigure(1, weight=1)
            phase = ctk.CTkLabel(prow, text=f"⚡ {j.phase or 'Working'}", font=T.F["meta"],
                                 text_color=T.WARN_HI)
            phase.grid(row=0, column=0, padx=(0, 10))
            bar = ctk.CTkProgressBar(prow, height=8, corner_radius=999, progress_color=T.ACCENT,
                                     fg_color=T.BG5)
            bar.grid(row=0, column=1, sticky="ew")
            bar.set(j.progress)
            pct = ctk.CTkLabel(prow, text=f"{int(j.progress*100)}%", font=T.F["monob"],
                               text_color=T.ACCENT, width=42)
            pct.grid(row=0, column=2, padx=10)
            meta = ctk.CTkLabel(prow, text=f"{j.speed or '—'} · ETA {j.eta or '—'}",
                                font=T.F["monosm"], text_color=T.FG5)
            meta.grid(row=0, column=3)
            self.running_refs = {"jid": j.id, "bar": bar, "pct": pct, "meta": meta, "phase": phase}

    def update_progress(self, job):
        if self.running_refs and self.running_refs["jid"] == job.id:
            self.running_refs["bar"].set(job.progress)
            self.running_refs["pct"].configure(text=f"{int(job.progress*100)}%")
            self.running_refs["meta"].configure(text=f"{job.speed or '—'} · ETA {job.eta or '—'}")
            self.running_refs["phase"].configure(text=f"⚡ {job.phase or 'Working'}")

    def _start(self):
        self.app.start_queue()

    def _toggle_pause(self):
        self.app.toggle_pause()
        self.refresh()

    def _move_up(self, j):
        self.app.move_job_up(j.id)
        self.refresh()

    def _save_queue(self):
        waiting = [j for j in self.state.jobs if j.status in ("waiting", "paused")]
        if not waiting:
            self.app.toast("No waiting jobs to save")
            return
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("Queue JSON", "*.json")], initialfile="queue.json")
        if not p:
            return
        data = [{"src_path": j.src_path, "src_type": j.src_type, "exfat": j.exfat,
                 "backend": j.backend, "level": j.level} for j in waiting]
        with open(p, "w") as f:
            json.dump(data, f, indent=2)
        self.app.toast(f"Saved {len(waiting)} jobs")
