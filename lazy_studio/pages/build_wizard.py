"""Build Wizard — a stepped Build flow that reuses the proven detection and
submission logic. This is the Build entry point (it replaced the legacy
AddJobPage, which has been removed).

Steps:
  1. Single or multiple builds
  2. Select source(s)        (folder / .exfat / .ffpkg as INPUT)
  3. Output format           (folder -> exFAT|FFPFSC; exfat/ffpkg -> FFPFSC only)
  4. Filename style + preview
  5. Summary
  6. Add to Queue / Start

This is UI only. It calls model-level helpers (extract_title_id, extract_version,
resolve_title, dir_size) and submits via app.add_job / app.start_queue. It does not
touch worker/job_runner/build logic, and never produces .ffpkg (no backend for it).
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import theme as T
from .. import models as M
from .. import preflight as PF
from ..widgets import Card, SegBar, Toggle
from .base import Page, primary_btn, ghost_btn, home_btn_large

STEPS = ["Build Type", "Select Files", "Output Format", "File Naming", "Review & Start"]

# Output formats offered per source type. .ffpkg is intentionally absent as an
# OUTPUT everywhere — there is no backend primitive that can create a .ffpkg.
OUTPUT_OPTS = {
    "folder": [("exFAT image", "exfat"), ("FFPFSC", "ffpfsc")],
    "exfat":  [("FFPFSC", "ffpfsc")],   # .exfat source -> .ffpfsc only
    "ffpkg":  [("FFPFSC", "ffpfsc")],   # .ffpkg source -> .ffpfsc only
}

# Human comparison info for the Output Format step. Purely descriptive — does not
# affect the build. "size_hint" is computed per source against the known source size.
FORMAT_INFO = {
    "exfat": {
        "title": "exFAT Image",
        "icon": "💿",
        "pros": ["Fastest to build — no compression pass",
                 "Direct, mountable image"],
        "cons": ["Largest output — same size as the game",
                 "Uses the most disk space"],
        "compression": "None",
        "speed": "Fastest",
    },
    "ffpfsc": {
        "title": "FFPFSC (compressed)",
        "icon": "📦",
        "pros": ["Smaller output — compressed image",
                 "Best for archiving / storage"],
        "cons": ["Slower to build — adds a compression pass",
                 "Final size can't be known until built"],
        "compression": "zlib (level from Settings)",
        "speed": "Slower",
    },
}


class _StagedSource:
    """One source queued in the wizard, with its detected metadata + choices."""

    def __init__(self, path: str, src_type: str):
        self.path = path
        self.src_type = src_type
        self.ppsa = ""
        self.title = ""
        self.version = ""
        self.size = 0
        self.files = 0
        # folder defaults to exfat-or-ffpfsc per settings; non-folder forced ffpfsc
        self.output_format = "ffpfsc"

    def detect(self):
        p = Path(self.path)
        self.ppsa = M.extract_title_id(str(p))
        self.version = M.extract_version(p.name)
        self.title = M.resolve_title(p, self.ppsa)
        try:
            if p.is_dir():
                self.size, self.files = M.dir_size(p)
            elif p.is_file():
                self.size, self.files = p.stat().st_size, 1
        except OSError:
            self.size, self.files = 0, 0


class BuildWizardPage(Page):
    def build(self):
        self.step = 0
        self.multi = False
        self.sources: list[_StagedSource] = []
        self.name_mode = getattr(self.state.settings, "name_mode", "ppsa_title_version")
        # Delete-source opt-in (default OFF). Plumbing only this slice — no deletion.
        self.delete_source = bool(getattr(self.state.settings, "delete_source", False))
        # Preflight state: last computed result + the inputs hash it was computed
        # for (so re-entering Summary without changes doesn't re-walk the dumps).
        self._pf_result = None
        self._pf_hash = None
        self._pf_running = False

        # Header: inline "Home" link above the title (more visible than the tiny
        # top-right control).
        home_btn_large(self, self.app)\
            .grid(row=0, column=0, sticky="w", padx=30, pady=(20, 0))
        ctk.CTkLabel(self, text="Build Image", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=30, pady=(8, 2))
        self.subtitle = ctk.CTkLabel(self, text="", font=T.F["body"], text_color=T.FG5, anchor="w")
        self.subtitle.grid(row=2, column=0, sticky="w", padx=30, pady=(0, 14))

        self.stepbar = ctk.CTkFrame(self, fg_color="transparent")
        self.stepbar.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 16))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=4, column=0, sticky="ew", padx=0)
        self.body.grid_columnconfigure(0, weight=1)

        self.navbar = ctk.CTkFrame(self, fg_color="transparent")
        self.navbar.grid(row=5, column=0, sticky="ew", padx=30, pady=(8, 30))
        self.navbar.grid_columnconfigure(1, weight=1)

        self._render()

    def on_show(self):
        self._render()

    # ── step rendering ────────────────────────────────────────
    def _render(self):
        self._render_stepbar()
        for w in self.body.winfo_children():
            w.destroy()
        for w in self.navbar.winfo_children():
            w.destroy()
        self._card_row = 0   # cards restack from the top each render
        [self._step_mode, self._step_sources, self._step_output,
         self._step_naming, self._step_summary][self.step]()
        self._render_nav()

    def _render_stepbar(self):
        for w in self.stepbar.winfo_children():
            w.destroy()
        for i, label in enumerate(STEPS):
            done = i < self.step
            active = i == self.step
            color = T.ACCENT if active else (T.SUCCESS if done else T.BG5)
            txtc = "#000" if (active or done) else T.FG5
            dot = ctk.CTkLabel(self.stepbar, text=str(i + 1), font=T.F["meta"], text_color=txtc,
                               fg_color=color, corner_radius=999, width=22, height=22)
            dot.grid(row=0, column=i * 2, padx=(0, 6))
            ctk.CTkLabel(self.stepbar, text=label, font=T.F["navb"] if active else T.F["nav"],
                         text_color=T.FG1 if active else T.FG5).grid(row=0, column=i * 2 + 1, padx=(0, 18))

    def _card(self, title):
        c = Card(self.body)
        # Stack cards top-to-bottom. Previously every card was gridded to row=0,
        # so a step with more than one card drew them on top of each other (e.g.
        # the Select-Files import buttons were hidden under the Sources list).
        r = getattr(self, "_card_row", 0)
        self._card_row = r + 1
        c.grid(row=r, column=0, sticky="ew", padx=30, pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        if title:
            ctk.CTkLabel(c, text=title, font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
                .grid(row=0, column=0, sticky="w", padx=22, pady=(16, 10))
        return c

    # Step 1 — Choose Build Type -------------------------------------------
    def _step_mode(self):
        self.subtitle.configure(text="Will you build one image, or queue several?")
        c = self._card("Build type")
        seg = SegBar(c, ["Single build", "Multiple builds"], [False, True],
                     default=self.multi, command=self._set_multi)
        seg.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 12))
        # Explain what each choice means (supports the overnight-queue use case).
        if not self.multi:
            head, body = "Single build", \
                "Build one game image. Best for testing or the occasional build."
        else:
            head, body = "Multiple builds", \
                ("Queue several games and run them back-to-back — ideal overnight. "
                 "Space is checked before starting so a long run won't fail late.")
        box = ctk.CTkFrame(c, fg_color=T.BG3, corner_radius=8)
        box.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 14))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=head, font=T.F["bodyb"], text_color=T.FG1, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(box, text=body, font=T.F["meta"], text_color=T.FG4, anchor="w",
                     justify="left", wraplength=560)\
            .grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

    def _set_multi(self, v):
        self.multi = v
        self._render()

    # Step 2 — Select Files ------------------------------------------------
    def _step_sources(self):
        self.subtitle.configure(
            text="Add one or more sources." if self.multi else "Add the source to build from.")
        # Import buttons — big, obvious, open the picker directly (no entry box).
        c = self._card("Add a source")
        btns = ctk.CTkFrame(c, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 6))
        for i in range(3):
            btns.grid_columnconfigure(i, weight=1, uniform="imp")
        primary_btn(btns, "📁  Add Dump Folder", lambda: self._import("folder"), height=44)\
            .grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ghost_btn(btns, "💿  Add exFAT Image", lambda: self._import("exfat"), height=44)\
            .grid(row=0, column=1, sticky="ew", padx=6)
        ghost_btn(btns, "📦  Add FFPKG Image", lambda: self._import("ffpkg"), height=44)\
            .grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(c, text="📁 Dump folder → exFAT or FFPFSC   ·   💿 exFAT image → FFPFSC   "
                             "·   📦 FFPKG image → FFPFSC  (FFPKG is input-only)",
                     font=T.F["meta"], text_color=T.FG5, anchor="w", wraplength=620, justify="left")\
            .grid(row=2, column=0, sticky="w", padx=22, pady=(2, 16))

        # Staged list with running totals.
        lc = self._card(f"Sources ({len(self.sources)})")
        if not self.sources:
            empty = ctk.CTkFrame(lc, fg_color=T.BG3, corner_radius=8)
            empty.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
            empty.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(empty, text="No sources yet", font=T.F["bodyb"], text_color=T.FG3)\
                .grid(row=0, column=0, pady=(14, 2))
            ctk.CTkLabel(empty, text="Use a button above to add a dump folder or image.",
                         font=T.F["meta"], text_color=T.FG6).grid(row=1, column=0, pady=(0, 14))
        else:
            for i, s in enumerate(self.sources):
                self._source_card(lc, i + 1, i, s)
            total = sum(s.size for s in self.sources)
            tline = ctk.CTkFrame(lc, fg_color="transparent")
            tline.grid(row=len(self.sources) + 1, column=0, sticky="ew", padx=22, pady=(6, 16))
            tline.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(tline, text=f"Total source size: {M.human_size(total)}",
                         font=T.F["bodyb"], text_color=T.FG1, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            pending = any(s.size == 0 for s in self.sources)
            if pending:
                ctk.CTkLabel(tline, text="(some sizes still calculating…)", font=T.F["meta"],
                             text_color=T.FG6, anchor="e").grid(row=0, column=1, sticky="e")

    def _import(self, src_type):
        """Open the right picker for the source type and add it immediately."""
        if src_type == "folder":
            p = filedialog.askdirectory(title="Select dump folder")
        else:
            ext = ".exfat" if src_type == "exfat" else ".ffpkg"
            p = filedialog.askopenfilename(title=f"Select {ext} file",
                                           filetypes=[(ext, f"*{ext}"), ("All files", "*.*")])
        if not p:
            return
        src = _StagedSource(p, src_type)
        src.output_format = "ffpfsc"   # folders can switch on the Output step; images are fixed
        if not self.multi:
            self.sources = [src]
        else:
            self.sources.append(src)
        self._detect_async(src)

    def _detect_async(self, src: _StagedSource):
        dq: "queue.Queue" = queue.Queue()

        def work():
            src.detect()
            dq.put(True)
        threading.Thread(target=work, daemon=True).start()
        self._poll_detect(dq)

    def _poll_detect(self, dq):
        try:
            dq.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_detect(dq))
            return
        self._render()

    def _source_card(self, parent, n, idx, s: _StagedSource):
        card = ctk.CTkFrame(parent, fg_color=T.BG3, corner_radius=6)
        card.grid(row=n, column=0, sticky="ew", padx=18, pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)
        type_label = {"folder": "Dump folder", "exfat": ".exfat image", "ffpkg": ".ffpkg image"}[s.src_type]
        ctk.CTkLabel(card, text={"folder": "🗂️", "exfat": "💿", "ffpkg": "📦"}[s.src_type],
                     font=T.F["title"]).grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=12)
        title = s.title or Path(s.path).name
        ctk.CTkLabel(card, text=f"{title}", font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
            .grid(row=0, column=1, sticky="w", pady=(12, 0))
        meta = f"{type_label} · {s.ppsa or '—'}"
        if s.version:
            meta += f" · v{s.version}"
        if s.size:
            meta += f" · {M.human_size(s.size)}"
        ctk.CTkLabel(card, text=meta, font=T.F["monosm"], text_color=T.FG5, anchor="w")\
            .grid(row=1, column=1, sticky="w", pady=(0, 12))
        ghost_btn(card, "✕", lambda i=idx: self._remove_source(i), height=28, width=10)\
            .grid(row=0, column=2, rowspan=2, padx=(8, 14))

    def _remove_source(self, idx):
        if 0 <= idx < len(self.sources):
            self.sources.pop(idx)
            self._render()

    # Step 3 — Output format ----------------------------------------------
    def _step_output(self):
        self.subtitle.configure(text="Choose what each source builds into.")
        if not self.sources:
            c = self._card("Output format")
            ctk.CTkLabel(c, text="Add a source first.", font=T.F["body"], text_color=T.FG5,
                         anchor="w").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))
            return
        for i, s in enumerate(self.sources):
            title = s.title or Path(s.path).name
            c = self._card(f"{title}")
            opts = OUTPUT_OPTS[s.src_type]
            grid = ctk.CTkFrame(c, fg_color="transparent")
            grid.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
            for col in range(len(opts)):
                grid.grid_columnconfigure(col, weight=1, uniform=f"of{i}")
            for col, (_lbl, val) in enumerate(opts):
                selectable = len(opts) > 1
                self._format_card(grid, col, s, val, selectable)
            if len(opts) == 1:
                src_kind = "exFAT" if s.src_type == "exfat" else "FFPKG"
                ctk.CTkLabel(c, text=f"📦 {src_kind} image source detected — output is FFPFSC "
                                     f"(image sources can only build to FFPFSC).",
                             font=T.F["meta"], text_color=T.ACCENT_HI, anchor="w",
                             wraplength=620, justify="left")\
                    .grid(row=2, column=0, sticky="w", padx=22, pady=(0, 14))

    def _format_card(self, parent, col, s, fmt, selectable):
        info = FORMAT_INFO[fmt]
        chosen = (s.output_format == fmt)
        border = T.ACCENT if chosen else T.BORDER2
        card = ctk.CTkFrame(parent, fg_color=T.BG3, border_color=border,
                            border_width=2 if chosen else 1, corner_radius=8)
        card.grid(row=0, column=col, sticky="nsew", padx=6, pady=2)
        card.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text=info["icon"], font=T.F["title"]).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(head, text=info["title"], font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
            .grid(row=0, column=1, sticky="w")
        if chosen:
            ctk.CTkLabel(head, text="✓ Selected", font=T.F["meta"], text_color="#000",
                         fg_color=T.ACCENT, corner_radius=999, padx=8, pady=1)\
                .grid(row=0, column=2, sticky="e")

        # estimated output size, computed against this source
        est = self._format_size_hint(s, fmt)
        ctk.CTkLabel(card, text=est, font=T.F["monosm"], text_color=T.ACCENT_HI, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))

        for txt in info["pros"]:
            ctk.CTkLabel(card, text=f"✓  {txt}", font=T.F["meta"], text_color=T.FG3, anchor="w",
                         justify="left", wraplength=260)\
                .grid(column=0, sticky="w", padx=14, pady=(0, 1))
        for txt in info["cons"]:
            ctk.CTkLabel(card, text=f"–  {txt}", font=T.F["meta"], text_color=T.FG5, anchor="w",
                         justify="left", wraplength=260)\
                .grid(column=0, sticky="w", padx=14, pady=(0, 1))
        ctk.CTkLabel(card, text=f"Compression: {info['compression']} · Build: {info['speed']}",
                     font=T.F["meta"], text_color=T.FG6, anchor="w")\
            .grid(column=0, sticky="w", padx=14, pady=(4, 10))

        if selectable:
            self._bind_card_click(card, lambda: self._set_src_format(s, fmt))

    def _format_size_hint(self, s, fmt):
        if not s.size:
            return "Output size: calculating…"
        if fmt == "exfat":
            return f"Output ≈ {M.human_size(s.size)} (uncompressed)"
        # ffpfsc: unknown until built; show a conservative range hint
        return f"Output ≤ {M.human_size(s.size)} (varies with compression)"

    def _bind_card_click(self, widget, fn):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _e: fn())
        for ch in widget.winfo_children():
            try:
                ch.configure(cursor="hand2")
            except Exception:
                pass
            ch.bind("<Button-1>", lambda _e: fn())

    def _set_src_format(self, src, v):
        src.output_format = v
        self._render()

    # Step 4 — Naming + preview -------------------------------------------
    def _step_naming(self):
        self.subtitle.configure(text="Name the output files. Preview updates live.")
        c = self._card("Filename style")
        SegBar(c, ["PPSA", "PPSA + Title", "PPSA + Title + Version"],
               ["ppsa", "ppsa_title", "ppsa_title_version"], default=self.name_mode,
               command=self._set_name_mode).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 14))

        if not self.sources:
            pc = self._card("Output preview")
            ctk.CTkLabel(pc, text="Add a source first.", font=T.F["body"], text_color=T.FG5,
                         anchor="w").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))
            return

        # One full preview card per source: filename, full path, type, source info.
        for s in self.sources:
            job = self._job_for(s)
            title = s.title or Path(s.path).name
            pc = self._card(title)
            inner = ctk.CTkFrame(pc, fg_color=T.BG1, border_color=T.BORDER1, border_width=1,
                                 corner_radius=6)
            inner.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
            inner.grid_columnconfigure(0, weight=1)

            def field(label, value, row, mono=True, color=T.FG2):
                ctk.CTkLabel(inner, text=label, font=T.F["meta"], text_color=T.FG5, anchor="w")\
                    .grid(row=row, column=0, sticky="w", padx=14, pady=(8 if row == 0 else 3, 0))
                ctk.CTkLabel(inner, text=value, font=T.F["mono"] if mono else T.F["body"],
                             text_color=color, anchor="w", justify="left", wraplength=620)\
                    .grid(row=row + 1, column=0, sticky="w", padx=14, pady=(0, 1))

            field("OUTPUT FILENAME", job.out_name, 0, color=T.ACCENT_HI)
            field("FULL OUTPUT PATH", str(job.final_output_path()), 2, color=T.FG3)
            otype = "exFAT image (uncompressed)" if s.output_format == "exfat" \
                else "FFPFSC (compressed)"
            field("OUTPUT TYPE", otype, 4, mono=False, color=T.FG2)
            src_sz = M.human_size(s.size) if s.size else "calculating…"
            field("SOURCE", f"{title} · {src_sz}", 6, mono=False, color=T.FG3)
            ctk.CTkFrame(inner, fg_color="transparent", height=4).grid(row=8, column=0)

        # Source handling — delete-after-success opt-in (default OFF, destructive).
        dc = self._card("Source handling")
        row = ctk.CTkFrame(dc, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 4))
        row.grid_columnconfigure(1, weight=1)
        Toggle(row, value=self.delete_source, command=self._set_delete_source)\
            .grid(row=0, column=0, padx=(0, 12))
        ctk.CTkLabel(row, text="Delete source after successful build", font=T.F["bodyb"],
                     text_color=T.FG1, anchor="w").grid(row=0, column=1, sticky="w")
        if self.delete_source:
            # Enabled = destructive. Show a filled amber warning row so it can't be
            # missed, with explicit "only after successful verify/move" wording.
            warn = ("⚠  Source will be deleted only after a successful verify/move. "
                    "The original dump/image is then permanently removed — this "
                    "cannot be undone. Turn this off if you're not certain.")
            ctk.CTkLabel(dc, text=warn, font=T.F["bodyb"], text_color="#000",
                         fg_color=T.WARN, corner_radius=6, anchor="w", justify="left",
                         wraplength=860)\
                .grid(row=2, column=0, sticky="ew", padx=22, pady=(6, 14),
                      ipady=8, ipadx=12)
        else:
            warn = ("Permanently deletes the original dump/image once the build fully "
                    "succeeds (after verify and move, when enabled). This cannot be "
                    "undone. Leave off unless you're sure.")
            ctk.CTkLabel(dc, text=warn, font=T.F["meta"], text_color=T.FG5, anchor="w",
                         justify="left", wraplength=620)\
                .grid(row=2, column=0, sticky="w", padx=22, pady=(2, 14))

    def _set_delete_source(self, v):
        self.delete_source = bool(v)
        self._render()

    def _set_name_mode(self, v):
        self.name_mode = v
        self._render()

    # Step 5 — Review & Start (Build Plan) ---------------------------------
    def _step_summary(self):
        self.subtitle.configure(text="Review the build plan, then add to the queue or start now.")
        c = self._card(f"Build plan — {len(self.sources)} build(s)")
        if not self.sources:
            ctk.CTkLabel(c, text="No sources to build.", font=T.F["body"], text_color=T.FG5,
                         anchor="w").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))
            return
        st = self.state.settings

        # Compact review table. Each source is ONE row (Game · PPSA · Output
        # filename · Format · Size) plus a small destination-folder detail line —
        # not a tall repeated form. The full output path is reconstructable from
        # the destination folder + the filename shown in the row. Per-row space
        # estimates and the destination/verify facts are intentionally NOT repeated
        # here: the global facts live in the summary line below and the space story
        # lives in the dedicated Space preflight panel. No filesystem work and no
        # PF.estimate_job — only cached source data is read (out_name/final_dir are
        # pure string/Path construction).
        table = ctk.CTkFrame(c, fg_color="transparent")
        table.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        table.grid_columnconfigure(0, weight=1)   # Game stretches
        # column header strip
        hdr = ctk.CTkFrame(table, fg_color=T.BG4, corner_radius=6)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        hdr.grid_columnconfigure(0, weight=1)
        cols = [("Game", 0, "w"), ("PPSA", 92, "w"), ("Output filename", 230, "w"),
                ("Format", 70, "w"), ("Size", 90, "e")]
        for i, (txt, w, anc) in enumerate(cols):
            hdr.grid_columnconfigure(i, weight=1 if i == 0 else 0)
            ctk.CTkLabel(hdr, text=txt.upper(), font=T.F["meta"], text_color=T.FG4, width=w,
                         anchor=anc).grid(row=0, column=i, sticky="ew", padx=(14, 8), pady=9)

        total = 0
        rr = 1
        for s in self.sources:
            job = self._job_for(s)
            fmt_label = "exFAT" if s.output_format == "exfat" else "FFPFSC"
            size_txt = M.human_size(s.size) if s.size else "…"
            dest = str(job.final_dir())   # destination FOLDER (pure Path, no FS access)

            row = ctk.CTkFrame(table, fg_color=T.BG3, corner_radius=6)
            row.grid(row=rr, column=0, sticky="ew", pady=(0, 4))
            row.grid_columnconfigure(0, weight=1)

            cells = ctk.CTkFrame(row, fg_color="transparent")
            cells.grid(row=0, column=0, sticky="ew", padx=(0, 0), pady=(8, 1))
            cells.grid_columnconfigure(0, weight=1)
            # Game (title; falls back to folder name) — stretches, ellipsised by wraplength
            ctk.CTkLabel(cells, text=(s.title or Path(s.path).name), font=T.F["bodyb"],
                         text_color=T.FG0, anchor="w", width=0, justify="left", wraplength=240)\
                .grid(row=0, column=0, sticky="w", padx=(14, 8))
            ctk.CTkLabel(cells, text=s.ppsa or "—", font=T.F["monosm"], text_color=T.FG3,
                         width=92, anchor="w").grid(row=0, column=1, sticky="w", padx=8)
            ctk.CTkLabel(cells, text=job.out_name, font=T.F["monosm"], text_color=T.ACCENT_HI,
                         width=230, anchor="w").grid(row=0, column=2, sticky="w", padx=8)
            ctk.CTkLabel(cells, text=fmt_label, font=T.F["monosm"], text_color=T.FG3,
                         width=70, anchor="w").grid(row=0, column=3, sticky="w", padx=8)
            ctk.CTkLabel(cells, text=size_txt, font=T.F["monob"], text_color=T.FG2,
                         width=90, anchor="e").grid(row=0, column=4, sticky="e", padx=(8, 14))
            # destination FOLDER detail line (not the full path; full path =
            # this folder + the filename in the row above)
            ctk.CTkLabel(row, text=f"→  {dest}", font=T.F["meta"], text_color=T.FG6,
                         anchor="w", justify="left", wraplength=900)\
                .grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))
            total += s.size
            rr += 1

        # Consolidated global facts on a single line (instead of repeating Verify /
        # Delete per source).
        delete_txt = "Yes" if self.delete_source else "No"
        facts_line = (f"Total source size: {M.human_size(total)}   ·   "
                      f"Verify after build: {'On' if st.verify else 'Off'}   ·   "
                      f"Delete source: {delete_txt}")
        ctk.CTkLabel(c, text=facts_line, font=T.F["meta"], text_color=T.FG4, anchor="w")\
            .grid(row=2, column=0, sticky="w", padx=22, pady=(4, 16))

        # Single delete-source warning section (shown once, not per source).
        if self.delete_source:
            warn = ("⚠  Delete source after build is ON — each source is permanently "
                    "removed only after its build verifies and moves successfully. "
                    "This cannot be undone.")
            wc = self._card("")
            ctk.CTkLabel(wc, text=warn, font=T.F["bodyb"], text_color="#000",
                         fg_color=T.WARN, corner_radius=6, anchor="w", justify="left",
                         wraplength=900)\
                .grid(row=0, column=0, sticky="ew", padx=18, pady=14, ipady=8, ipadx=12)

        # Space preflight (off-thread; cached against a source/settings hash).
        # Unchanged: reads the cached async result and (re)triggers the threaded
        # preflight. No synchronous estimate work happens on this thread.
        self._render_preflight()
        self._maybe_run_preflight()

    def _stages_for(self, s):
        """Human build-stage names for a source/output combination."""
        if s.output_format == "exfat":
            stages = ["Scan", "Create exFAT"]
        elif s.src_type == "folder":
            stages = ["Scan", "Create exFAT", "Compress"]
        else:  # image source -> ffpfsc (no temp exFAT)
            stages = ["Scan", "Compress"]
        if self.state.settings.verify and s.output_format == "ffpfsc":
            stages.append("Verify")
        if self.state.settings.ssd_staging and self.state.settings.move_after:
            stages.append("Move to archive")
        return stages

    # ── preflight (space estimation) ─────────────────────────
    def _preflight_hash(self):
        """A stable signature of everything that affects the space estimate, so we
        only re-walk the dumps when something relevant changed."""
        st = self.state.settings
        srcs = tuple((s.path, s.src_type, s.output_format) for s in self.sources)
        env = (st.staging_path, st.archive_path, bool(st.ssd_staging), bool(st.move_after))
        return hash((srcs, env))

    def _estimate_for(self, idx):
        """Return the cached JobEstimate for source index `idx`, or None.

        Returns an estimate ONLY when a completed preflight result exists AND it was
        computed for the CURRENT inputs (hash match). This is the stale-guard: if the
        user changed/removed sources or went Back and altered something, the old
        estimates are ignored (the Review step shows 'Checking space…' until the
        re-triggered background preflight lands). check_queue() builds estimates in
        job order == source order, so we align by index, bounded by a length check so
        a stale/partial result can never mis-index onto the wrong source.

        Crucially this performs NO filesystem work — it only reads already-computed
        results, so it is safe to call on the UI thread during render.
        """
        res = self._pf_result
        if res is None or self._pf_running:
            return None
        if self._pf_hash != self._preflight_hash():
            return None  # cached estimates are for different inputs — treat as stale
        ests = getattr(res, "estimates", None) or []
        if idx < 0 or idx >= len(ests) or len(ests) != len(self.sources):
            return None  # length mismatch -> don't risk pairing the wrong estimate
        return ests[idx]

    def _maybe_run_preflight(self):
        if not self.sources:
            return
        h = self._preflight_hash()
        if self._pf_result is not None and self._pf_hash == h:
            return  # cached result is still valid
        if self._pf_running:
            return  # a run is already in flight
        self._pf_running = True
        jobs = [self._job_for(s) for s in self.sources]
        dq: "queue.Queue" = queue.Queue()

        def work():
            try:
                res = PF.check_queue(jobs)
            except Exception:
                res = None
            dq.put(res)
        threading.Thread(target=work, daemon=True).start()
        self._poll_preflight(dq, h)

    def _poll_preflight(self, dq, h):
        try:
            res = dq.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_preflight(dq, h))
            return
        self._pf_running = False
        self._pf_result = res
        self._pf_hash = h
        current = self._preflight_hash()
        if h != current:
            # Inputs changed while this preflight was in flight (user added/removed/
            # changed a source, or went Back and altered something). The result we
            # just stored is stale for the current inputs — _estimate_for() will
            # reject it by hash, so the Review step keeps showing 'Checking space…'.
            # Re-render now; _step_summary's tail calls _maybe_run_preflight(), which
            # starts a fresh preflight for the current inputs (its own guards prevent
            # a duplicate run).
            if self.step == len(STEPS) - 1:
                self._render()
            return
        # Result is for the current inputs. Re-render only if still on Summary
        # (user may have navigated away); the re-render is cheap now — it reads the
        # cached estimates via _estimate_for and performs no filesystem work.
        if self.step == len(STEPS) - 1:
            self._render()

    def _vol_role(self, label: str) -> str:
        """Human role for a volume path: Staging / Archive / Output."""
        st = self.state.settings
        path = label.split(" (+")[0]
        roles = []
        try:
            if Path(path) == Path(st.staging_path) or path.startswith(str(Path(st.staging_path))):
                roles.append("Staging")
            if Path(path) == Path(st.archive_path) or path.startswith(str(Path(st.archive_path))):
                roles.append("Archive")
        except Exception:
            pass
        return " / ".join(roles) if roles else "Drive"

    def _render_preflight(self):
        pc = self._card("Space preflight")
        res = self._pf_result
        if res is None or self._pf_running:
            ctk.CTkLabel(pc, text="⏳  Calculating space requirements…", font=T.F["body"],
                         text_color=T.FG4, anchor="w").grid(row=1, column=0, sticky="w",
                                                            padx=22, pady=(0, 18))
            return
        # status banner
        banner = {PF.PASS: ("✓  Sufficient space for this build queue.", T.SUCCESS, "#000"),
                  PF.WARN: ("⚠  May be tight — estimate assumes no compression. You can still proceed.",
                            T.WARN, "#000"),
                  PF.BLOCK: ("✕  Insufficient space — the exact image size exceeds free space.",
                             T.DANGER, "#fff")}[res.status]
        b = ctk.CTkLabel(pc, text=banner[0], font=T.F["bodyb"], text_color=banner[2],
                         fg_color=banner[1], corner_radius=6, anchor="w", justify="left")
        b.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12), ipady=8, ipadx=12)

        # per-volume rows: role · required · free · status
        rr = 2
        for v in res.volumes:
            role = self._vol_role(v.label)
            row = ctk.CTkFrame(pc, fg_color=T.BG3, corner_radius=6)
            row.grid(row=rr, column=0, sticky="ew", padx=18, pady=(0, 8))
            row.grid_columnconfigure(1, weight=1)
            glyph = {PF.PASS: "✅", PF.WARN: "⚠️", PF.BLOCK: "❌"}[v.status]
            ctk.CTkLabel(row, text=glyph, font=T.F["body"]).grid(row=0, column=0, padx=(14, 10), pady=12)
            ctk.CTkLabel(row, text=f"{role}", font=T.F["bodyb"], text_color=T.FG1, anchor="w")\
                .grid(row=0, column=1, sticky="w")
            free_txt = M.human_size(v.free) if v.free is not None else "unknown"
            ctk.CTkLabel(row, text=f"needs ~{M.human_size(v.required)} · {free_txt} free",
                         font=T.F["monosm"], text_color=T.FG4, anchor="e")\
                .grid(row=0, column=2, sticky="e", padx=(8, 14))
            rr += 1
        ctk.CTkLabel(pc, text=("Staging shows the largest single build (builds run one at a time); "
                               "Archive shows the total of all finished outputs."),
                     font=T.F["meta"], text_color=T.FG6, anchor="w", justify="left", wraplength=620)\
            .grid(row=rr, column=0, sticky="w", padx=22, pady=(4, 16))

    # ── job construction (reuses model + name_mode) ──────────
    def _job_for(self, s: _StagedSource) -> M.BuildJob:
        st = self.state.settings
        j = M.BuildJob(src_path=s.path, src_type=s.src_type, backend=st.backend, level=st.level,
                       cpu_count=st.cpu_count(), exfat=st.exfat, ssd_staging=st.ssd_staging,
                       staging_path=st.staging_path, archive_path=st.archive_path,
                       move_after=st.move_after, verify=st.verify, ram_streaming=st.ram_streaming)
        j.ppsa = s.ppsa
        j.title = s.title
        j.version = s.version
        j.size_bytes = s.size
        j.file_count = s.files
        j.output_format = s.output_format
        j.name_mode = self.name_mode
        j.delete_source = self.delete_source
        return j

    # ── nav / submit ─────────────────────────────────────────
    def _render_nav(self):
        # Back (except step 0)
        if self.step > 0:
            ghost_btn(self.navbar, "← Back", self._back).grid(row=0, column=0, sticky="w")
        if self.step < len(STEPS) - 1:
            # Disable Next on the Select-Files step until at least one source exists.
            blocked = self.step == 1 and not self.sources
            nxt = primary_btn(self.navbar, "Next →", self._next)
            nxt.grid(row=0, column=2, sticky="e")
            if blocked:
                nxt.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)
        else:
            # Summary step: submit actions.
            can = bool(self.sources)
            # Add to Queue stays enabled even on BLOCK — deferring a build that
            # doesn't currently fit is legitimate (user may free space first).
            primary_btn(self.navbar, "✚  Add to Queue",
                        (lambda: self._submit(False)) if can else self._noop).grid(
                            row=0, column=2, sticky="e", padx=(0, 10))
            # Start Now is hard-disabled only when preflight returns BLOCK (exact
            # requirement exceeds free space). WARN remains overridable.
            res = self._pf_result
            hard_block = bool(can and res is not None and res.status == PF.BLOCK)
            start = primary_btn(self.navbar, "▶  Start Now",
                                self._blocked_start if hard_block else
                                ((lambda: self._submit(True)) if can else self._noop),
                                color=T.SUCCESS, text_color="#fff")
            start.grid(row=0, column=3, sticky="e")
            if hard_block:
                start.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)

    def _blocked_start(self):
        self.app.toast("Not enough free space to start now — free space or add to queue")

    def _noop(self):
        self.app.toast("Add at least one source first")

    def _back(self):
        self.step = max(0, self.step - 1)
        self._render()

    def _next(self):
        # Guard: need a source before leaving the Sources step
        if self.step == 1 and not self.sources:
            self.app.toast("Add at least one source first")
            return
        self.step = min(len(STEPS) - 1, self.step + 1)
        self._render()

    def _submit(self, start: bool):
        if not self.sources:
            self.app.toast("Add at least one source first")
            return
        # Submit every staged source. Use add_job(start=False) for all, then a
        # single start_queue() so a multi-build runs as one batch. This reuses the
        # existing, hardened submission + auto-navigation paths.
        for s in self.sources:
            self.app.add_job(self._job_for(s), start=False)
        if start:
            self.app.start_queue()   # navigates to Active Build
        else:
            self.app.show_page("queue")
        # reset the wizard for next time
        self.sources = []
        self.step = 0
