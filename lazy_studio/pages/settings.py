"""Advanced Settings: compression, performance, SSD staging, integrity."""
from __future__ import annotations
import webbrowser
from tkinter import filedialog
import customtkinter as ctk
from .. import theme as T
from .. import models as M
from ..widgets import Card, SegBar, Toggle, Stepper
from .base import Page, field_entry, ghost_btn, home_btn_large


class SettingsPage(Page):
    def build(self):
        s = self.state.settings
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 8))
        head.grid_columnconfigure(0, weight=1)
        home_btn_large(head, self.app).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ctk.CTkLabel(head, text="Advanced Settings", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(head, text="Defaults applied to every new build job.", font=T.F["body"],
                     text_color=T.FG5, anchor="w").grid(row=2, column=0, sticky="w", pady=(2, 0))

        # ── compression ──
        c = self._card(2, "Compression")
        ctk.CTkLabel(c, text="Backend", font=T.F["label"], text_color=T.FG4, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=22, pady=(0, 2))
        ctk.CTkLabel(c, text="Compression engine for FFPFSC images. ISA-L is faster on supported CPUs; "
                            "zlib is the universal fallback.", font=T.F["meta"], text_color=T.FG5,
                     anchor="w", justify="left", wraplength=620)\
            .grid(row=2, column=0, sticky="w", padx=22, pady=(0, 1))
        # Recommended + Default on one compact line (accent + dim).
        self._rec_default(c, 3, "zlib for maximum compatibility", "Intel ISA-L", pad=(0, 6))
        SegBar(c, [M.BACKEND_LABELS[b] for b in M.BACKENDS], M.BACKENDS, default=s.backend,
               command=lambda v: self._set("backend", v)).grid(row=4, column=0, sticky="w", padx=22)
        lr = ctk.CTkFrame(c, fg_color="transparent")
        lr.grid(row=5, column=0, sticky="ew", padx=22, pady=(10, 0))
        lr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lr, text="Compression level", font=T.F["label"], text_color=T.FG4, anchor="w")\
            .grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lr, text="1 = fastest · 9 = smallest", font=T.F["meta"],
                     text_color=T.FG6).grid(row=0, column=1, sticky="e")
        self._rec_default(c, 6, "6 balanced; lower is faster, higher is smaller/slower", "3",
                          pad=(2, 6))
        SegBar(c, [str(i) for i in range(1, 10)], list(range(1, 10)), default=s.level, min_w=48,
               command=lambda v: self._set("level", v)).grid(row=7, column=0, sticky="ew", padx=22, pady=(0, 14))

        # ── performance ──
        p = self._card(3, "Performance")
        self._row(p, 1, "Compression workers",
                  "CPU threads used by the current build. Auto = cores − 1.",
                  lambda parent: SegBar(parent, M.COMP_WORKER_CHOICES, M.COMP_WORKER_CHOICES,
                                        default=s.comp_workers, min_w=54,
                                        command=lambda v: self._set("comp_workers", v)), border=True,
                  rec="4–8 on most systems; higher only if CPU/RAM allows.", default="Auto")
        self._row(p, 3, "Concurrent jobs",
                  "Games built at once. 1 is safest for 100–300 GB images.",
                  lambda parent: Stepper(parent, value=s.concurrent_jobs, lo=1, hi=4,
                                         command=lambda v: self._set("concurrent_jobs", v)), border=True,
                  rec="1 for large images; 2 only with fast NVMe and lots of free space.", default="1")
        self._row(p, 5, "RAM streaming",
                  "Stream compression directly — no temp spool files. Off forces disk spooling.",
                  lambda parent: Toggle(parent, value=s.ram_streaming,
                                        command=lambda v: self._set("ram_streaming", v)),
                  rec="Off unless you have plenty of RAM.", default="On")

        # ── ssd staging ──
        st = self._card(4, "SSD Staging")
        self._row(st, 1, "Build & compress on staging SSD",
                  "Use a fast NVMe scratch drive for the heavy IO, then relocate the finished image.",
                  lambda parent: Toggle(parent, value=s.ssd_staging,
                                        command=lambda v: self._set("ssd_staging", v)),
                  icon="⚡", border=True,
                  rec="On, use NVMe/SSD for faster temporary builds.", default="On")
        paths = ctk.CTkFrame(st, fg_color="transparent")
        paths.grid(row=3, column=0, sticky="ew", padx=22, pady=(8, 10))
        paths.grid_columnconfigure(0, weight=1, uniform="p")
        paths.grid_columnconfigure(1, weight=1, uniform="p")
        self.stage_entry = self._path_field(paths, 0, "Staging drive", s.staging_path,
                                            lambda v: self._set("staging_path", v))
        self.archive_entry = self._path_field(paths, 1, "Final archive folder", s.archive_path,
                                              lambda v: self._set("archive_path", v))
        self._row(st, 4, "Move to archive on completion",
                  "Relocate the finished image off the SSD automatically to free staging space.",
                  lambda parent: Toggle(parent, value=s.move_after,
                                        command=lambda v: self._set("move_after", v)),
                  icon="📦", rec="On if archive folder is slower/larger storage.", default="On")

        # ── integrity ──
        ig = self._card(5, "Integrity")
        self._row(ig, 1, "Verify after build",
                  "Low-RAM block-by-block hash check of the finished image. Catches bad reads & bit-rot.",
                  lambda parent: Toggle(parent, value=s.verify,
                                        command=lambda v: self._set("verify", v)), icon="🛡️",
                  rec="On for FFPFSC; skipped for exFAT.", default="On")

        nm = self._card(6, "Naming")
        self._row(nm, 1, "Output filename style",
                  "How new build output files are named. Applies to .exfat, .ffpfsc and .ffpfs.",
                  lambda parent: SegBar(parent,
                                        ["PPSA", "PPSA + Title", "PPSA + Title + Version"],
                                        ["ppsa", "ppsa_title", "ppsa_title_version"],
                                        default=getattr(s, "name_mode", "ppsa_title_version"),
                                        command=lambda v: self._set("name_mode", v)), icon="🏷️",
                  rec="PPSA + Title + Version.", default="PPSA + Title + Version")

        # ── build logs ──
        bl = self._card(7, "Build Logs")
        self._row(bl, 1, "Save build logs",
                  "Write a .txt log (with metadata header) for every build — handy "
                  "for diagnosing a build someone reports as stuck.",
                  lambda parent: Toggle(parent, value=getattr(s, "save_logs", False),
                                        command=lambda v: self._set("save_logs", v)),
                  icon="📝", border=True,
                  rec="On if you want a record of each build.", default="Off")
        logpaths = ctk.CTkFrame(bl, fg_color="transparent")
        logpaths.grid(row=3, column=0, sticky="ew", padx=22, pady=(8, 12))
        logpaths.grid_columnconfigure(0, weight=1)
        self.logs_entry = self._path_field(
            logpaths, 0, "Log folder (leave blank to use <archive>/logs)",
            getattr(s, "logs_path", ""), lambda v: self._set("logs_path", v))

        # ── when the queue finishes ──
        pq = self._card(8, "When the Queue Finishes")
        self._row(pq, 1, "Post-queue action",
                  "Optionally sleep or shut down the PC after the whole queue "
                  "finishes — only if every build succeeded (no errors or "
                  "cancellations). A 60-second countdown lets you cancel.",
                  lambda parent: SegBar(parent, ["Do nothing", "Sleep", "Shutdown"],
                                        ["nothing", "sleep", "shutdown"],
                                        default=getattr(s, "post_queue_action", "nothing"),
                                        command=lambda v: self._set("post_queue_action", v)),
                  icon="🌙",
                  rec="Do nothing, unless running large overnight batches.",
                  default="Do nothing")

        # ── credits & support ──
        cr = self._card(9, "Credits & Support")
        ctk.CTkLabel(cr, text="Thank you Nazky for the LazyMkPFS backend that powers this tool.",
                     font=T.F["body"], text_color=T.FG2, anchor="w", justify="left",
                     wraplength=820).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 8))
        # Support Nazky
        n_row = ctk.CTkFrame(cr, fg_color="transparent")
        n_row.grid(row=2, column=0, sticky="w", padx=22, pady=(0, 4))
        ctk.CTkLabel(n_row, text="Support Nazky:", font=T.F["meta"], text_color=T.FG5,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._link(n_row, 0, 1, "github.com/Nazky", "https://github.com/Nazky")
        # Support this project
        m_row = ctk.CTkFrame(cr, fg_color="transparent")
        m_row.grid(row=3, column=0, sticky="w", padx=22, pady=(0, 8))
        ctk.CTkLabel(m_row, text="Support this project:", font=T.F["meta"], text_color=T.FG5,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._link(m_row, 0, 1, "github.com/kerrdec97", "https://github.com/kerrdec97")
        ctk.CTkLabel(m_row, text="·", font=T.F["meta"], text_color=T.FG6)\
            .grid(row=0, column=2, sticky="w", padx=8)
        self._link(m_row, 0, 3, "ko-fi.com/deckerr9746220",
                   "https://ko-fi.com/deckerr9746220")
        ctk.CTkLabel(cr, text="Any support is massively appreciated.", font=T.F["meta"],
                     text_color=T.FG4, anchor="w").grid(row=4, column=0, sticky="w",
                                                        padx=22, pady=(0, 8))
        # Copy debug info — makes bug reports (esp. on Linux) far easier.
        dbg_row = ctk.CTkFrame(cr, fg_color="transparent")
        dbg_row.grid(row=5, column=0, sticky="w", padx=22, pady=(0, 14))
        self._dbg_btn = ghost_btn(dbg_row, "📋  Copy debug info", self._copy_debug_info, height=32)
        self._dbg_btn.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(dbg_row, text="OS · Python · architecture · version · backend",
                     font=T.F["meta"], text_color=T.FG6, anchor="w")\
            .grid(row=0, column=1, sticky="w", padx=(10, 0))

    # ── builders ──────────────────────────────────────────────
    def _copy_debug_info(self):
        """Copy a plain-text system-info block to the clipboard for bug reports."""
        try:
            info = M.system_debug_info(self.state.settings)
            self.clipboard_clear()
            self.clipboard_append(info)
            self._dbg_btn.configure(text="✓  Copied")
            self.after(1500, lambda: self._dbg_btn.configure(text="📋  Copy debug info"))
        except Exception:
            try:
                self.app.toast("Could not copy debug info")
            except Exception:
                pass

    def _open_url(self, url: str):
        """Open a (hardcoded, trusted) URL in the default browser. Guarded so a
        missing browser / locked-down environment can never crash the app."""
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _link(self, parent, row, col, text, url):
        """A clickable link label: accent-coloured, hand cursor, opens url on click.
        Uses the same cursor+bind pattern as the rest of the app (no native
        hyperlink widget exists in CTk)."""
        lbl = ctk.CTkLabel(parent, text=text, font=T.F["meta"], text_color=T.ACCENT_HI,
                           anchor="w", cursor="hand2")
        lbl.grid(row=row, column=col, sticky="w")
        lbl.bind("<Button-1>", lambda _e, u=url: self._open_url(u))
        lbl.bind("<Enter>", lambda _e: lbl.configure(text_color=T.ACCENT))
        lbl.bind("<Leave>", lambda _e: lbl.configure(text_color=T.ACCENT_HI))
        return lbl

    def _rec_default(self, parent, grid_row, rec, default, pad=(1, 0)):
        """Render 'Recommended: <x>  ·  Default: <y>' as TWO labels on ONE row, so
        Recommended keeps its accent colour and Default stays dim — while costing a
        single line instead of two. Purely presentational; no values change."""
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.grid(row=grid_row, column=0, sticky="w", padx=22, pady=pad)
        col = 0
        if rec:
            ctk.CTkLabel(line, text=f"Recommended: {rec}", font=T.F["meta"],
                         text_color=T.ACCENT_HI, anchor="w", justify="left")\
                .grid(row=0, column=col, sticky="w")
            col += 1
        if rec and default:
            ctk.CTkLabel(line, text="·", font=T.F["meta"], text_color=T.FG6)\
                .grid(row=0, column=col, sticky="w", padx=8)
            col += 1
        if default:
            ctk.CTkLabel(line, text=f"Default: {default}", font=T.F["meta"],
                         text_color=T.FG6, anchor="w", justify="left")\
                .grid(row=0, column=col, sticky="w")
        return line

    def _card(self, grid_row, title):
        c = Card(self)
        c.grid(row=grid_row, column=0, sticky="ew", padx=30, pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(c, text=title.upper(), font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=22, pady=(14, 8))
        return c

    def _row(self, parent, grid_row, title, desc, control_factory, icon=None, border=False,
             rec=None, default=None):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=grid_row, column=0, sticky="ew", padx=22, pady=(0, 8))
        # Stable 3-column layout: icon (fixed) · text (stretch) · control (fixed, right).
        wrap.grid_columnconfigure(0, weight=0)
        wrap.grid_columnconfigure(1, weight=1)
        wrap.grid_columnconfigure(2, weight=0)
        if icon:
            ctk.CTkLabel(wrap, text=icon, font=T.F["statlg"]).grid(row=0, column=0, padx=(0, 12))
        txt = ctk.CTkFrame(wrap, fg_color="transparent")
        txt.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(txt, text=title, font=T.F["bodyb"], text_color=T.FG1, anchor="w")\
            .grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(txt, text=desc, font=T.F["meta"], text_color=T.FG5, anchor="w", justify="left")\
            .grid(row=1, column=0, sticky="w")
        # Recommended + Default share ONE line (two labels, accent + dim) instead of
        # two stacked rows — same information, less height. Additive help only; never
        # changes defaults or behaviour.
        if rec or default:
            line = ctk.CTkFrame(txt, fg_color="transparent")
            line.grid(row=2, column=0, sticky="w", pady=(1, 0))
            col = 0
            if rec:
                ctk.CTkLabel(line, text=f"Recommended: {rec}", font=T.F["meta"],
                             text_color=T.ACCENT_HI, anchor="w", justify="left")\
                    .grid(row=0, column=col, sticky="w")
                col += 1
            if rec and default:
                ctk.CTkLabel(line, text="·", font=T.F["meta"], text_color=T.FG6)\
                    .grid(row=0, column=col, sticky="w", padx=8)
                col += 1
            if default:
                ctk.CTkLabel(line, text=f"Default: {default}", font=T.F["meta"],
                             text_color=T.FG6, anchor="w", justify="left")\
                    .grid(row=0, column=col, sticky="w")
        # Build the control with wrap as its REAL parent — never cross-parent via in_=,
        # which clips CTk composite widgets to the wrong canvas and hides them.
        control = control_factory(wrap)
        control.grid(row=0, column=2, sticky="e")
        if border:
            ln = ctk.CTkFrame(parent, fg_color=T.BORDER1, height=1)
            ln.grid(row=grid_row + 1, column=0, sticky="ew", padx=22, pady=(0, 8))
        return control

    def _path_field(self, parent, col, label, value, on_set):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 7, 7 if col == 0 else 0))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=label, font=T.F["label"], text_color=T.FG4, anchor="w")\
            .grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        e = field_entry(box, value)
        e.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        e.bind("<FocusOut>", lambda ev: on_set(e.get().strip()))

        def browse():
            p = filedialog.askdirectory(title=label)
            if p:
                e.delete(0, "end")
                e.insert(0, p)
                on_set(p)
        ghost_btn(box, "📂", browse, width=42, height=36).grid(row=1, column=1)
        return e

    def _set(self, key, value):
        setattr(self.state.settings, key, value)
        self.state.settings.save()
