"""Edit exFAT Image — Slice A: mount read-only + browse. No edits are made.

UI over the headless image_edit service. The user opens an .exfat image, mounts
it read-only, browses its contents and properties, and unmounts. There is no
write capability here — this is the safe scaffold for future edit slices.
"""
from __future__ import annotations

import threading
import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import theme as T
from .. import models as M
from .. import image_edit as IE
from ..widgets import Card
from .base import Page, primary_btn, ghost_btn, home_btn_large


def _open_path(path: str):
    """Open a directory (or drive root) directly in the OS file manager. Unlike
    history._open_in_explorer (which opens a file's *parent*), this opens the path
    itself — used for the mounted drive root. Read-only: just a shell open."""
    import os
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: SLF001
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class EditImagePage(Page):
    def build(self):
        self.image_path: str = ""
        self.session: IE.MountSession | None = None
        self.state_name = "idle"   # idle | mounting | mounted | unmounting | unmount_failed | error
        self.message = ""
        self.props: IE.Properties | None = None
        self.cwd: str = ""         # current dir being browsed (under the mount root)
        self.session_warning = ""  # non-fatal warning shown while still mounted
        self._health_token = 0     # increments to cancel stale health-poll loops

        home_btn_large(self, self.app)\
            .grid(row=0, column=0, sticky="w", padx=30, pady=(20, 0))
        ctk.CTkLabel(self, text="Edit exFAT Image", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w", padx=30, pady=(8, 2))
        ctk.CTkLabel(self, text="Read-only mode — no edits are made.", font=T.F["body"],
                     text_color=T.WARN, anchor="w")\
            .grid(row=2, column=0, sticky="w", padx=30, pady=(0, 14))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=3, column=0, sticky="nsew", padx=30, pady=(0, 30))
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._render()

    def on_show(self):
        self._render()

    # ── render ────────────────────────────────────────────────
    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        # Linux/macOS guard: Edit Image is OSFMount + Windows-drive-letter based, so
        # it can't mount on other platforms. Show a clear "Windows only" message
        # instead of attempting a mount that would fail. (No build-pipeline change —
        # this only affects the read-only browse feature.)
        import sys as _sys
        if not _sys.platform.startswith("win"):
            self._render_windows_only()
            return
        self._render_source_bar()
        # Empty-state guidance: idle, nothing mounted, and no image picked yet.
        # Explains the read-only / non-destructive contract and offers the open CTA,
        # instead of leaving a bare page under the source bar.
        if self.state_name == "idle" and self.session is None and not self.image_path:
            self._render_empty()
        if self.state_name == "error" and self.message:
            self._banner(self.message, T.DANGER, "#fff")
        # Info message (e.g. external unmount detected) shown in the idle state.
        if self.state_name == "idle" and self.message:
            self._banner(self.message, T.INFO_BG, T.ACCENT_HI)
        if self.state_name == "mounting":
            self._banner("⏳ Mounting image read-only…", T.INFO_BG, T.ACCENT_HI)
        if self.state_name == "unmounting":
            self._banner(self.message or "⏏ Unmounting…", T.INFO_BG, T.ACCENT_HI)
        # A non-fatal warning (e.g. unmount failed) shown ABOVE the still-visible
        # mounted view, so the user keeps properties/files and can retry Unmount.
        if self.session is not None and self.session_warning:
            self._banner(self.session_warning, T.WARN, "#000")
        if self.session is not None and self.state_name in ("mounted", "unmounting", "unmount_failed"):
            self._render_properties()
            self._render_browser()

    def _banner(self, text, bg, fg):
        b = ctk.CTkLabel(self.body, text=text, font=T.F["bodyb"], text_color=fg, fg_color=bg,
                         corner_radius=6, anchor="w", justify="left", wraplength=900)
        b.grid(sticky="ew", pady=(0, 10), ipady=8, ipadx=12)

    def _render_windows_only(self):
        """Shown on non-Windows: Edit Image needs OSFMount and isn't available yet.
        A clear message beats attempting a mount that can only fail."""
        c = Card(self.body)
        c.grid(sticky="ew", pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(c, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=20, pady=(30, 30))
        inner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(inner, text="🪟", font=T.F["h1"], text_color=T.FG5)\
            .grid(row=0, column=0, pady=(0, 6))
        ctk.CTkLabel(inner, text="Edit Image is Windows-only for now",
                     font=T.F["h2"], text_color=T.FG2).grid(row=1, column=0, pady=(0, 4))
        ctk.CTkLabel(inner, text=("This feature currently requires OSFMount and is "
                                  "only available on Windows. Linux support is planned "
                                  "in a future release.\n\nBuilding and compressing "
                                  "images works normally on this platform — only the "
                                  "read-only Edit/browse view is unavailable."),
                     font=T.F["body"], text_color=T.FG5, justify="center", wraplength=560)\
            .grid(row=2, column=0)

    def _render_empty(self):
        """Idle empty-state card: explains the read-only, non-destructive contract
        and offers the Open CTA. Mount/read-only behaviour itself is unchanged —
        this is presentation only."""
        c = Card(self.body)
        c.grid(sticky="ew", pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(c, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 26))
        inner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(inner, text="🔒", font=T.F["h1"], text_color=T.FG5)\
            .grid(row=0, column=0, pady=(0, 6))
        ctk.CTkLabel(inner, text="Open an exFAT image to browse it read-only",
                     font=T.F["h2"], text_color=T.FG2).grid(row=1, column=0, pady=(0, 2))
        ctk.CTkLabel(inner, text=("The image is mounted read-only — the original "
                                  "file is never modified. Browse its properties and "
                                  "files, then unmount when you're done."),
                     font=T.F["body"], text_color=T.FG5, justify="center", wraplength=560)\
            .grid(row=2, column=0, pady=(0, 16))
        primary_btn(inner, "📂  Open .exfat Image", self._open, height=36)\
            .grid(row=3, column=0)

    def _render_source_bar(self):
        c = Card(self.body)
        c.grid(sticky="ew", pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(c, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=18, pady=14)
        inner.grid_columnconfigure(0, weight=1)
        label = self.image_path or "No image selected"
        ctk.CTkLabel(inner, text=label, font=T.F["mono"], text_color=T.FG2 if self.image_path else T.FG5,
                     anchor="w", wraplength=520, justify="left").grid(row=0, column=0, sticky="w")

        mounted = self.session is not None
        if mounted:
            # When mounted, users want to inspect the live filesystem — open the
            # mounted drive root in Explorer, not re-pick the image file.
            ghost_btn(inner, "📂  Open Mounted Drive",
                      lambda: _open_path(self.session.root), height=34)\
                .grid(row=0, column=1, padx=(8, 6))
            ctk.CTkLabel(inner, text=f"Mounted: {self.session.drive}", font=T.F["bodyb"],
                         text_color=T.SUCCESS, anchor="e").grid(row=0, column=2, padx=(0, 8))
            ub = primary_btn(inner, "⏏  Unmount", self._unmount, height=34, color=T.DANGER,
                             text_color="#fff")
            ub.grid(row=0, column=3)
            if self.state_name == "unmounting":
                ub.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)
        else:
            ghost_btn(inner, "📂  Open .exfat Image", self._open, height=34)\
                .grid(row=0, column=1, padx=(8, 6))
            mb = primary_btn(inner, "🔒  Mount Read-Only", self._mount, height=34)
            mb.grid(row=0, column=2)
            if not self.image_path or self.state_name == "mounting":
                mb.configure(state="disabled", fg_color=T.BG5, text_color=T.FG6)

    def _render_properties(self):
        p = self.props or IE.Properties()
        c = Card(self.body)
        c.grid(sticky="ew", pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(c, text="PROPERTIES", font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=22, pady=(18, 8))

        # Metadata first (most useful), then capacity split into Used/Free/Total.
        rows = []
        if p.has_param:
            rows += [
                ("Title", p.title or "—"),
                ("PPSA", p.ppsa or "—"),
                ("Version", p.version or "—"),
                ("Content ID", p.content_id or "—"),
            ]
        rows += [
            ("Drive", self.session.drive if self.session else "—"),
            ("Used Space", M.human_size(p.used)),
            ("Free Space", M.human_size(p.free)),
            ("Total Size", M.human_size(p.total)),
        ]
        if not p.has_param:
            rows.append(("Metadata", "No sce_sys/param.json found (not a PS5 dump image)"))

        table = ctk.CTkFrame(c, fg_color="transparent")
        table.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
        table.grid_columnconfigure(1, weight=1)
        for i, (k, v) in enumerate(rows):
            bg = T.BG3 if i % 2 else "transparent"
            kl = ctk.CTkLabel(table, text=k, font=T.F["meta"], text_color=T.FG5, anchor="w",
                              fg_color=bg, width=120, corner_radius=4)
            kl.grid(row=i, column=0, sticky="ew", padx=(0, 1), pady=1, ipady=4, ipadx=8)
            vl = ctk.CTkLabel(table, text=v, font=T.F["monosm"], text_color=T.FG2, anchor="w",
                              fg_color=bg, wraplength=720, justify="left", corner_radius=4)
            vl.grid(row=i, column=1, sticky="ew", pady=1, ipady=4, ipadx=8)

    def _render_browser(self):
        c = Card(self.body)
        c.grid(sticky="nsew", pady=(0, 10))
        c.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(c, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="FILES", font=T.F["eyebrow"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w")
        # breadcrumb / up button
        root = self.session.root if self.session else ""
        rel = self._rel(self.cwd, root)
        ctk.CTkLabel(hdr, text=("\\" + rel) if rel else "\\ (root)", font=T.F["monosm"],
                     text_color=T.FG4, anchor="w").grid(row=0, column=1, sticky="w", padx=10)
        if rel:
            ghost_btn(hdr, "⬆ Up", self._up, height=26, width=10).grid(row=0, column=2, sticky="e")

        listing = IE.list_dir(self.cwd) if self.cwd else []
        if not listing:
            ctk.CTkLabel(c, text="(empty)", font=T.F["body"], text_color=T.FG5, anchor="w")\
                .grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))
            return
        # Column header row (matches _entry_row column widths).
        chead = ctk.CTkFrame(c, fg_color=T.BG4, corner_radius=4)
        chead.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 2))
        chead.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(chead, text="NAME", font=T.F["meta"], text_color=T.FG5, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=(12, 8), pady=6)
        ctk.CTkLabel(chead, text="SIZE", font=T.F["meta"], text_color=T.FG5, anchor="e", width=90)\
            .grid(row=0, column=2, padx=6)
        ctk.CTkLabel(chead, text="MODIFIED", font=T.F["meta"], text_color=T.FG5, anchor="e", width=130)\
            .grid(row=0, column=3, padx=(6, 12))
        wrap = ctk.CTkScrollableFrame(c, fg_color="transparent", height=320,
                                      scrollbar_fg_color=T.BG2,
                                      scrollbar_button_color=T.BG4,
                                      scrollbar_button_hover_color=T.BORDER3)
        wrap.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        wrap.grid_columnconfigure(0, weight=1)
        for i, e in enumerate(listing):
            self._entry_row(wrap, i, e)

    def _entry_row(self, parent, i, e: IE.Entry):
        row = ctk.CTkFrame(parent, fg_color=T.BG3 if i % 2 else "transparent", corner_radius=4)
        row.grid(row=i, column=0, sticky="ew", pady=1)
        row.grid_columnconfigure(1, weight=1)
        icon = "📁" if e.is_dir else "📄"
        name = ctk.CTkLabel(row, text=f"{icon}  {e.name}", font=T.F["mono"],
                            text_color=T.FG1 if e.is_dir else T.FG2, anchor="w")
        name.grid(row=0, column=0, sticky="w", padx=(10, 8), pady=5)
        meta = "" if e.is_dir else M.human_size(e.size)
        when = ""
        try:
            import datetime
            when = datetime.datetime.fromtimestamp(e.mtime).strftime("%Y-%m-%d %H:%M") if e.mtime else ""
        except Exception:
            when = ""
        ctk.CTkLabel(row, text=meta, font=T.F["monosm"], text_color=T.FG5, anchor="e", width=90)\
            .grid(row=0, column=2, padx=6)
        ctk.CTkLabel(row, text=when, font=T.F["monosm"], text_color=T.FG6, anchor="e", width=130)\
            .grid(row=0, column=3, padx=(6, 12))
        if e.is_dir:
            for w in (row, name):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda _ev, p=e.path: self._enter_dir(p))

    # ── helpers ───────────────────────────────────────────────
    def _rel(self, path, root):
        try:
            if not path or not root:
                return ""
            return str(Path(path).relative_to(Path(root)))
        except Exception:
            return ""

    def _enter_dir(self, path):
        self.cwd = path
        self._render()

    def _up(self):
        if not self.session:
            return
        root = Path(self.session.root)
        cur = Path(self.cwd)
        if cur != root and root in cur.parents:
            self.cwd = str(cur.parent)
            self._render()

    # ── actions ───────────────────────────────────────────────
    def _open(self):
        p = filedialog.askopenfilename(title="Select .exfat image",
                                       filetypes=[(".exfat image", "*.exfat"), ("All files", "*.*")])
        if p:
            self.image_path = p
            self.state_name = "idle"
            self.message = ""
            self._render()

    def _mount(self):
        if not self.image_path or self.session is not None:
            return
        self.state_name = "mounting"
        self.message = ""
        self._render()
        dq: "queue.Queue" = queue.Queue()

        def work():
            try:
                sess = IE.mount_readonly(self.image_path)
                props = IE.read_properties(sess.root)
                dq.put(("ok", sess, props))
            except IE.MountError as e:
                dq.put(("err", str(e), None))
            except Exception as e:  # noqa: BLE001
                dq.put(("err", f"Unexpected error: {e}", None))
        threading.Thread(target=work, daemon=True).start()
        self._poll_mount(dq)

    def _poll_mount(self, dq):
        try:
            kind, a, b = dq.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_mount(dq))
            return
        if kind == "ok":
            self.session = a
            self.props = b
            self.cwd = a.root
            self.session_warning = ""
            self.state_name = "mounted"
            self.message = ""
            self._render()
            self._start_health_poll()   # detect external unmount while mounted
            return
        else:
            self.session = None
            self.state_name = "error"
            self.message = a
        self._render()

    def _unmount(self):
        if self.session is None or self.state_name == "unmounting":
            return
        sess = self.session
        # IMPORTANT: do NOT tear down the mounted view here. Clearing the UI before
        # OSFMount actually detaches caused (a) a blank/flicker and (b) loss of the
        # mounted view when unmount failed. Instead we keep properties/files visible,
        # release only app-side *data* handles (no rendered widget holds an OS file
        # handle — os.scandir closes per-listing and we never chdir into the mount),
        # flip to a controlled 'unmounting' status, and clear the UI only AFTER a
        # confirmed successful detach (in _poll_unmount).
        self._set_status("unmounting", "⏏ Unmounting…")
        import gc
        gc.collect()
        self.update_idletasks()

        dq: "queue.Queue" = queue.Queue()

        def work():
            ok, msg = IE.unmount(sess)
            dq.put((ok, msg))
        threading.Thread(target=work, daemon=True).start()
        self._poll_unmount(dq)

    def _poll_unmount(self, dq):
        try:
            ok, msg = dq.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_unmount(dq))
            return
        if ok:
            # Detach confirmed — NOW it's safe to clear the mounted view.
            self._reset_to_idle()
        else:
            # Detach failed: keep the session, keep Mounted state + the Unmount
            # button, keep properties/files visible, and surface the warning.
            self.session_warning = msg
            self._set_status("mounted", "")
            self._render()
    # ── controlled state transitions ──────────────────────────
    def _set_status(self, state, message):
        """Single point for status changes, so transitions are controlled and the
        render stays consistent (avoids ad-hoc blanking)."""
        self.state_name = state
        self.message = message
        self._render()

    def _reset_to_idle(self):
        """Clear all mounted state after a confirmed detach (or external unmount)
        and stop the health poll."""
        self._health_token += 1   # cancel any in-flight health loop
        self.session = None
        self.props = None
        self.cwd = ""
        self.session_warning = ""
        self.state_name = "idle"
        self.message = ""
        self._render()

    # ── mounted-drive health poll (detect external unmount) ───
    def _start_health_poll(self):
        """Begin polling the mounted drive ~every 1.5s. If the drive vanishes
        (e.g. user detached it in OSFMount outside the app), reset to a clean
        unmounted state with an info message. Cancels itself when not mounted."""
        self._health_token += 1
        token = self._health_token
        self.after(1500, lambda: self._health_check(token))

    def _health_check(self, token):
        # Stale loop (a newer poll started, or we unmounted) — stop silently.
        if token != self._health_token:
            return
        if self.session is None or self.state_name not in ("mounted", "unmount_failed"):
            return
        if not IE.drive_alive(self.session.root):
            # Drive disappeared out from under us — treat as externally unmounted.
            self._reset_to_idle()
            self._set_status("idle", "")
            self.session_warning = ""
            self.message = "ℹ The mounted drive was removed (unmounted outside the app)."
            self._render()
            return
        # Still alive — schedule the next check.
        self.after(1500, lambda: self._health_check(token))
