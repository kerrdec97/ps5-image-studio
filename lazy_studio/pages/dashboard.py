"""Overview: workstation monitoring page (Last Build, Queue, Storage, Recent
Outputs, Quick Actions).

This is a monitoring surface, not the build entry point — the Build Wizard owns
that now. Everything here is presentation over existing state (appstate, history,
settings, storage); no worker/build-pipeline contact. The internal routing key
remains "dashboard" so navigation is unchanged; only the visible label is
"Overview".
"""
from __future__ import annotations

import shutil
from pathlib import Path

import customtkinter as ctk

from .. import theme as T
from .. import models as M
from ..widgets import Card, LogView
from .base import Page, primary_btn, ghost_btn, home_btn_large
from .history import _open_in_explorer

# Low-space warning threshold (free bytes). Below this, Storage flags the volume.
LOW_SPACE_BYTES = 20 * 1024 * 1024 * 1024   # 20 GB


class DashboardPage(Page):
    def build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(18, 10))
        head.grid_columnconfigure(0, weight=1)
        home_btn_large(head, self.app).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ctk.CTkLabel(head, text="Overview", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w")
        self.sub = ctk.CTkLabel(head, text="", font=T.F["body"], text_color=T.FG5, anchor="w")
        self.sub.grid(row=2, column=0, sticky="w", pady=(2, 0))
        primary_btn(head, "⚡  New Build", lambda: self.app.enter_mode("build"))\
            .grid(row=1, column=1, rowspan=2, sticky="e")

        # Section holders, re-rendered on refresh.
        self.last_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.last_holder.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 6))
        self.last_holder.grid_columnconfigure(0, weight=1)

        # Build Health KPI strip (full-width row of small tiles).
        self.health_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.health_holder.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 6))
        self.health_holder.grid_columnconfigure(0, weight=1)

        # Row: Queue Snapshot | Build Defaults (two info cards).
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 6))
        info.grid_columnconfigure(0, weight=1, uniform="i")
        info.grid_columnconfigure(1, weight=1, uniform="i")
        self.snapshot_holder = ctk.CTkFrame(info, fg_color="transparent")
        self.snapshot_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.snapshot_holder.grid_columnconfigure(0, weight=1)
        self.defaults_holder = ctk.CTkFrame(info, fg_color="transparent")
        self.defaults_holder.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.defaults_holder.grid_columnconfigure(0, weight=1)

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 6))
        mid.grid_columnconfigure(0, weight=1, uniform="m")
        mid.grid_columnconfigure(1, weight=1, uniform="m")
        self.storage_holder = ctk.CTkFrame(mid, fg_color="transparent")
        self.storage_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.storage_holder.grid_columnconfigure(0, weight=1)
        self.actions_holder = ctk.CTkFrame(mid, fg_color="transparent")
        self.actions_holder.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.actions_holder.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=28, pady=(0, 20))
        bottom.grid_columnconfigure(0, weight=1)
        self.recent_holder = ctk.CTkFrame(bottom, fg_color="transparent")
        self.recent_holder.grid(row=0, column=0, sticky="nsew")
        self.recent_holder.grid_columnconfigure(0, weight=1)

    # ── dynamic ───────────────────────────────────────────────
    def _section_header(self, card, text, row=0):
        """Consistent, tight section header used by every Overview card."""
        ctk.CTkLabel(card, text=text, font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
            .grid(row=row, column=0, sticky="w", padx=18, pady=(15, 6))

    def refresh(self):
        st = self.state
        running = st.running()
        waiting = st.waiting() if hasattr(st, "waiting") else \
            [j for j in st.jobs if j.status in ("waiting", "paused")]
        wait_bytes = sum(j.size_bytes for j in waiting)
        self.sub.configure(text=f"{len(st.jobs)} jobs · {M.human_size(wait_bytes)} queued · "
                                f"{'1 building now' if running else 'idle'}")
        self._build_last()
        self._build_health(running, waiting, wait_bytes)
        self._build_snapshot(waiting)
        self._build_defaults()
        self._build_storage()
        self._build_actions()
        self._build_recent()

    def _success_stats(self):
        """(success_rate_pct or None, last_gain_str or None) from history."""
        hist = self.state.history
        if not hist:
            return None, None
        done = sum(1 for h in hist if getattr(h, "outcome", "done") == "done")
        rate = round(100 * done / len(hist))
        last_gain = None
        for h in hist:
            g = (h.gain or "").strip()
            if g and g not in ("—", "-"):
                last_gain = g if g.endswith("%") else f"{g}"
                break
        return rate, last_gain

    # ── A. Last Build ─────────────────────────────────────────
    def _last_build_info(self):
        """Normalise the last build from either appstate.last_finished (a live
        BuildJob, session-only) or history[0] (a persisted HistoryEntry). Returns
        a dict with a 'source' marker, or None if there's nothing to show."""
        lf = getattr(self.state, "last_finished", None)
        if lf is not None:
            is_exfat = getattr(lf, "output_format", "ffpfsc") == "exfat" or lf.out_ext == ".exfat"
            return {
                "source": "job",
                "title": lf.title or Path(lf.src_path).name,
                "ppsa": lf.ppsa,
                "status": getattr(lf, "status", "done"),
                "fmt": "exFAT image" if is_exfat else "FFPFSC",
                "size_gain": (f"{M.human_size(lf.size_bytes)} → exFAT" if is_exfat
                              else f"gain {lf.gain:.1f}%" if getattr(lf, "gain", 0) else "—"),
                "elapsed": M.fmt_secs(getattr(lf, "elapsed", 0)),
                "final_path": getattr(lf, "final_path", "") or "",
                "src_path": lf.src_path,
                "src_type": lf.src_type,
                "log": list(getattr(lf, "log", []) or []),
                "log_path": getattr(lf, "log_path", "") or "",
            }
        hist = self.state.history
        if hist:
            h = hist[0]
            ext = (h.out_ext or "").lower()
            return {
                "source": "history",
                "title": h.name,
                "ppsa": h.ppsa,
                "status": getattr(h, "outcome", "done"),
                "fmt": "exFAT image" if ext == ".exfat" else "FFPFSC",
                "size_gain": h.sizes if h.gain in ("—", "") else f"gain {h.gain}",
                "elapsed": h.time,
                "final_path": h.final_path,
                "src_path": h.src_path,
                "src_type": h.src_type,
                "log": list(h.log or []),
                "log_path": getattr(h, "log_path", "") or "",
            }
        return None

    def _build_last(self):
        for w in self.last_holder.winfo_children():
            w.destroy()
        # Last Build is the primary section — give it a subtle accent border so it
        # reads as the focal point above the secondary grid below. Corner radius
        # matches the other cards (8) so it leads by accent, not by size.
        card = ctk.CTkFrame(self.last_holder, fg_color=T.BG2, border_color=T.ACCENT,
                            border_width=1, corner_radius=8)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "LAST BUILD")
        info = self._last_build_info()
        if info is None:
            ctk.CTkLabel(card, text="No builds yet — start your first build.", font=T.F["body"],
                         text_color=T.FG5, anchor="w").grid(row=1, column=0, sticky="w",
                                                            padx=18, pady=(0, 16))
            return
        status = info["status"]
        glyph = {"done": "✅", "error": "❌", "cancelled": "⏹"}.get(status, "✅")
        ctk.CTkLabel(card, text=f"{glyph}  {info['title']}", font=T.F["h2"], text_color=T.FG0,
                     anchor="w").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 6))

        # Compact metric tiles instead of one long meta line.
        metrics = ctk.CTkFrame(card, fg_color="transparent")
        metrics.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        cells = [
            ("Output", info["fmt"]),
            ("PPSA", info["ppsa"] or "—"),
            ("Result", info["size_gain"]),
            ("Duration", info["elapsed"]),
        ]
        for i in range(len(cells)):
            metrics.grid_columnconfigure(i, weight=1, uniform="lbm")
        for i, (label, value) in enumerate(cells):
            cell = ctk.CTkFrame(metrics, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="w")
            ctk.CTkLabel(cell, text=label.upper(), font=T.F["meta"], text_color=T.FG6, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(cell, text=value, font=T.F["monosm"], text_color=T.FG2, anchor="w")\
                .grid(row=1, column=0, sticky="w", pady=(1, 0))
        if info["final_path"]:
            ctk.CTkLabel(card, text=info["final_path"], font=T.F["meta"], text_color=T.FG6,
                         anchor="w", wraplength=900, justify="left")\
                .grid(row=3, column=0, sticky="w", padx=18, pady=(0, 8))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="w", padx=18, pady=(2, 12))
        has_out = bool(info["final_path"])
        ob = ghost_btn(btns, "📂  Open Folder",
                       lambda p=info["final_path"]: _open_in_explorer(p) if p else None, height=32)
        ob.grid(row=0, column=0, padx=(0, 8))
        if not has_out:
            ob.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)
        ghost_btn(btns, "📋  View Log",
                  lambda i=info: self._show_log(i["title"], i["log"], i.get("log_path", "")),
                  height=32).grid(row=0, column=1, padx=(0, 8))
        rb = ghost_btn(btns, "🔄  Rebuild",
                       lambda i=info: self._rebuild(i["src_path"], i["src_type"]), height=32)
        rb.grid(row=0, column=2)
        if not info["src_path"]:
            rb.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)

    # ── B. Build Health (KPI tiles) ───────────────────────────
    def _build_health(self, running, waiting, wait_bytes):
        for w in self.health_holder.winfo_children():
            w.destroy()
        card = Card(self.health_holder)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "BUILD HEALTH")
        rate, last_gain = self._success_stats()
        tiles = ctk.CTkFrame(card, fg_color="transparent")
        tiles.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 16))
        kpis = [
            ("🟢" if not running else "⚡", "Status", "Building" if running else "Idle",
             T.WARN_HI if running else T.SUCCESS),
            ("📦", "Queue", f"{len(waiting)} waiting", T.FG1),
            ("💾", "Total Waiting", M.human_size(wait_bytes) if wait_bytes else "—", T.FG1),
            ("📈", "Success Rate", f"{rate}%" if rate is not None else "—", T.ACCENT_HI),
            ("⚡", "Last Gain", last_gain if last_gain else "—", T.SUCCESS),
        ]
        for i in range(len(kpis)):
            tiles.grid_columnconfigure(i, weight=1, uniform="kpi")
        for i, (icon, label, value, color) in enumerate(kpis):
            t = ctk.CTkFrame(tiles, fg_color=T.BG3, corner_radius=7)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            t.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(t, text=f"{icon}  {label}", font=T.F["meta"], text_color=T.FG5,
                         anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(11, 0))
            ctk.CTkLabel(t, text=value, font=T.F["monob"], text_color=color, anchor="w")\
                .grid(row=1, column=0, sticky="w", padx=12, pady=(2, 12))

    # ── Queue Snapshot (next job) ─────────────────────────────
    def _build_snapshot(self, waiting):
        for w in self.snapshot_holder.winfo_children():
            w.destroy()
        card = Card(self.snapshot_holder)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "NEXT JOB")
        if not waiting:
            ctk.CTkLabel(card, text="Queue is empty.", font=T.F["body"], text_color=T.FG5,
                         anchor="w").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 16))
            ghost_btn(card, "▤  View Queue", lambda: self.app.show_page("queue"), height=30)\
                .grid(row=2, column=0, sticky="w", padx=18, pady=(0, 16))
            return
        nxt = waiting[0]
        fmt = "exFAT image" if getattr(nxt, "output_format", "ffpfsc") == "exfat" else "FFPFSC"
        ctk.CTkLabel(card, text=nxt.display_name, font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=18)
        rows = [("PPSA", nxt.ppsa or "—"), ("Format", fmt), ("Size", M.human_size(nxt.size_bytes))]
        rr = 2
        for k, v in rows:
            line = ctk.CTkFrame(card, fg_color="transparent")
            line.grid(row=rr, column=0, sticky="ew", padx=18, pady=(2, 0))
            line.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(line, text=k, font=T.F["meta"], text_color=T.FG5, anchor="w", width=70)\
                .grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(line, text=v, font=T.F["monosm"], text_color=T.FG2, anchor="w")\
                .grid(row=0, column=1, sticky="w")
            rr += 1
        cnt = f"{len(waiting)} in queue" if len(waiting) > 1 else "only job in queue"
        ctk.CTkLabel(card, text=cnt, font=T.F["meta"], text_color=T.FG6, anchor="w")\
            .grid(row=rr, column=0, sticky="w", padx=18, pady=(8, 0))
        ghost_btn(card, "▤  View Queue", lambda: self.app.show_page("queue"), height=30)\
            .grid(row=rr + 1, column=0, sticky="w", padx=18, pady=(8, 16))

    # ── Build Defaults summary ────────────────────────────────
    def _build_defaults(self):
        for w in self.defaults_holder.winfo_children():
            w.destroy()
        s = self.state.settings
        card = Card(self.defaults_holder)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "CURRENT DEFAULTS")
        workers = "Auto" if getattr(s, "comp_workers", "Auto") == "Auto" else str(s.comp_workers)
        rows = [
            ("Backend", f"{s.backend} L{s.level}"),
            ("Workers", workers),
            ("Verify", "On" if s.verify else "Off"),
            ("SSD Staging", "On" if s.ssd_staging else "Off"),
            ("Delete Source", "On" if getattr(s, "delete_source", False) else "Off"),
        ]
        rr = 1
        for k, v in rows:
            line = ctk.CTkFrame(card, fg_color="transparent")
            line.grid(row=rr, column=0, sticky="ew", padx=18, pady=(2, 0))
            line.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(line, text=k, font=T.F["meta"], text_color=T.FG5, anchor="w", width=110)\
                .grid(row=0, column=0, sticky="w")
            vcolor = T.WARN if (k == "Delete Source" and v == "On") else T.FG2
            ctk.CTkLabel(line, text=v, font=T.F["monosm"], text_color=vcolor, anchor="w")\
                .grid(row=0, column=1, sticky="w")
            rr += 1
        ghost_btn(card, "⚙  Settings", lambda: self.app.show_page("settings"), height=30)\
            .grid(row=rr, column=0, sticky="w", padx=18, pady=(8, 16))

    # ── C. Storage ────────────────────────────────────────────
    def _free_bytes(self, path):
        try:
            p = Path(path)
            probe = p if p.exists() else (Path(p.anchor) if p.anchor else Path.home())
            usage = shutil.disk_usage(str(probe))
            return usage.free, usage.total
        except Exception:
            return None, None

    def _same_volume(self, a, b):
        """Best-effort same-volume check, reusing preflight's volume identity."""
        try:
            from .. import preflight as PF
            return PF._volume_id(Path(a)) == PF._volume_id(Path(b))
        except Exception:
            return False

    def _build_storage(self):
        for w in self.storage_holder.winfo_children():
            w.destroy()
        st = self.state.settings
        card = Card(self.storage_holder)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "STORAGE")

        r = 1
        for label, path in (("Staging", st.staging_path), ("Archive", st.archive_path)):
            free, total = self._free_bytes(path)
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.grid(row=r, column=0, sticky="ew", padx=18, pady=(0, 12))
            row.grid_columnconfigure(0, weight=1)
            low = free is not None and free < LOW_SPACE_BYTES
            ctk.CTkLabel(row, text=label, font=T.F["bodyb"], text_color=T.FG2, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            if free is not None and total:
                used_frac = max(0.0, min(1.0, (total - free) / total))
                pct_used = round(used_frac * 100)
                pct_free = 100 - pct_used
                bar = ctk.CTkProgressBar(row, height=10, corner_radius=999,
                                         progress_color=T.WARN if low else T.ACCENT, fg_color=T.BG5)
                bar.grid(row=1, column=0, sticky="ew", pady=(4, 3))
                bar.set(used_frac)
                detail = (f"{M.human_size(free)} free / {M.human_size(total)} · {pct_free}% free")
                ctk.CTkLabel(row, text=detail, font=T.F["monosm"],
                             text_color=T.WARN if low else T.FG5, anchor="w")\
                    .grid(row=2, column=0, sticky="w")
            else:
                ctk.CTkLabel(row, text="free space unknown", font=T.F["monosm"],
                             text_color=T.FG5, anchor="w").grid(row=1, column=0, sticky="w")
            if low:
                ctk.CTkLabel(row, text="⚠ Low space", font=T.F["meta"], text_color=T.WARN,
                             anchor="w").grid(row=3, column=0, sticky="w", pady=(2, 0))
            ctk.CTkLabel(row, text=str(path), font=T.F["meta"], text_color=T.FG6, anchor="w",
                         wraplength=360, justify="left").grid(row=4, column=0, sticky="w", pady=(2, 0))
            r += 1

        if self._same_volume(st.staging_path, st.archive_path):
            ctk.CTkLabel(card, text="ℹ Staging and Archive are on the same drive.",
                         font=T.F["meta"], text_color=T.FG5, anchor="w")\
                .grid(row=r, column=0, sticky="w", padx=18, pady=(4, 0))
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", height=4).grid(row=r, column=0)

    # ── D. Recent Outputs ─────────────────────────────────────
    def _build_recent(self):
        for w in self.recent_holder.winfo_children():
            w.destroy()
        card = Card(self.recent_holder)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "RECENT OUTPUTS")
        done = [h for h in self.state.history if getattr(h, "outcome", "done") == "done"][:6]
        if not done:
            ctk.CTkLabel(card, text="No completed builds yet.", font=T.F["body"],
                         text_color=T.FG5, anchor="w").grid(row=1, column=0, sticky="w",
                                                            padx=18, pady=(0, 18))
            return
        r = 1
        for h in done:
            ext = (h.out_ext or "").lower()
            otype = "exFAT" if ext == ".exfat" else "FFPFSC"
            row = ctk.CTkFrame(card, fg_color=T.BG3, corner_radius=6)
            row.grid(row=r, column=0, sticky="ew", padx=18, pady=(0, 5))
            row.grid_columnconfigure(0, weight=1)
            # Single line: name (bold) + dim meta, actions on the right.
            line = ctk.CTkFrame(row, fg_color="transparent")
            line.grid(row=0, column=0, sticky="ew", padx=14, pady=7)
            line.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(line, text=h.name, font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(line, text=f"{h.ppsa or '—'} · {otype} · {h.when}", font=T.F["monosm"],
                         text_color=T.FG5, anchor="w").grid(row=0, column=1, sticky="e", padx=(10, 8))
            act = ctk.CTkFrame(line, fg_color="transparent")
            act.grid(row=0, column=2, sticky="e")
            ob = ctk.CTkButton(act, text="📂", font=T.F["meta"], fg_color=T.BG5,
                               hover_color=T.BORDER3, text_color=T.FG3, height=26, width=10,
                               corner_radius=4, command=lambda p=h.final_path: _open_in_explorer(p))
            ob.pack(side="left", padx=2)
            if not h.final_path:
                ob.configure(state="disabled", text_color=T.FG6)
            rb = ctk.CTkButton(act, text="🔄", font=T.F["meta"], fg_color=T.BG5,
                               hover_color=T.BORDER3, text_color=T.FG3, height=26, width=10,
                               corner_radius=4,
                               command=lambda e=h: self._rebuild(e.src_path, e.src_type))
            rb.pack(side="left", padx=2)
            if not h.src_path:
                rb.configure(state="disabled", text_color=T.FG6)
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", height=4).grid(row=r, column=0)

    # ── E. Quick Actions ──────────────────────────────────────
    def _build_actions(self):
        for w in self.actions_holder.winfo_children():
            w.destroy()
        card = Card(self.actions_holder)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "QUICK ACTIONS")
        primary_btn(card, "⚡  New Build", lambda: self.app.enter_mode("build"))\
            .grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        ghost_btn(card, "🕓  History", lambda: self.app.show_page("history"))\
            .grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        ghost_btn(card, "⚙  Settings", lambda: self.app.show_page("settings"))\
            .grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))
        diag = ghost_btn(card, "🩺  Diagnostics (soon)", lambda: None)
        diag.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        diag.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)

    # ── shared actions (reused by Last Build + Recent Outputs) ─
    def _rebuild(self, src_path, src_type):
        if not src_path:
            self.app.toast("No source path recorded for this build")
            return
        self.app.add_job_from_path(src_path, src_type=src_type)
        self.app.show_page("queue")

    def _show_log(self, title, log, log_path=""):
        # Prefer the saved .txt log on disk; fall back to the in-app popup.
        from .history import _open_file
        if _open_file(log_path):
            return
        win = ctk.CTkToplevel(self)
        win.title(f"Build log — {title}")
        win.geometry("760x520")
        win.configure(fg_color=T.BG1)
        lv = LogView(win)
        lv.pack(fill="both", expand=True, padx=12, pady=12)
        for ln in (log or ["(no log captured)"]):
            lv.add(ln)
