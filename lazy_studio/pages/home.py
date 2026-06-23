"""Home / mode-select screen — the v2 front door.

Full-window frame shown at launch, layered over the app body. Presents large
mode cards; clicking an enabled card calls app.enter_mode(<page_key>) which hides
Home, shows the existing shell, and routes via show_page. Edit/Diagnostics are
deliberately disabled ("Coming soon") — no fake functionality.

This is pure UI. It does not touch worker/build/queue logic and is never routed
through show_page (it lives outside the sidebar registry).
"""
from __future__ import annotations

import customtkinter as ctk

from .. import theme as T
from ..widgets import Card

class HomeFrame(ctk.CTkFrame):
    """Mode-select front door. Sibling to the app body; toggled by the app.

    Three visual tiers: Build Image as a hero (primary), History + Settings
    (secondary), Edit Image + Diagnostics (tertiary / coming soon).
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG1, corner_radius=0)
        self.app = app
        self._build()

    def _build(self):
        # Centered column, capped width, so cards don't sprawl on wide windows.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=0, column=0)

        ctk.CTkLabel(wrap, text="🎮  PS5 Image Studio", font=T.F["h1"],
                     text_color=T.FG0).grid(row=0, column=0, pady=(0, 2))
        ctk.CTkLabel(wrap, text="PS5 Image Workstation — choose what you'd like to do",
                     font=T.F["body"], text_color=T.FG4).grid(row=1, column=0, pady=(0, 26))

        # Tier 1 — Build Image as a wide hero card (the primary action).
        self._hero(wrap, 2)

        # Tier 2 — core workspaces: Overview, Queue, Active Build.
        core = ctk.CTkFrame(wrap, fg_color="transparent")
        core.grid(row=3, column=0, pady=(14, 0))
        for c in range(3):
            core.grid_columnconfigure(c, weight=1, uniform="core")
        self._tile(core, 0, "dashboard", "▦", "Overview", "Status, storage & recent builds", True, big=True)
        self._tile(core, 1, "queue", "▤", "Queue", "Pending & batch builds", True, big=True)
        self._tile(core, 2, "active", "⚡", "Active Build", "Live build progress", True, big=True)

        # Tier 3 — History, Settings, Edit Image.
        sec = ctk.CTkFrame(wrap, fg_color="transparent")
        sec.grid(row=4, column=0, pady=(10, 0))
        for c in range(3):
            sec.grid_columnconfigure(c, weight=1, uniform="sec")
        self._tile(sec, 0, "history", "🕓", "History", "View & rebuild past builds", True, big=False)
        self._tile(sec, 1, "settings", "⚙", "Settings", "Workstation defaults", True, big=False)
        import sys as _sys
        _edit_sub = "Mount & browse (read-only)" if _sys.platform.startswith("win") \
            else "Windows only for now"
        self._tile(sec, 2, "edit", "✎", "Edit exFAT Image", _edit_sub, True, big=False)

        # Tier 4 — Diagnostics (tertiary, coming soon).
        ter = ctk.CTkFrame(wrap, fg_color="transparent")
        ter.grid(row=5, column=0, pady=(10, 0))
        ter.grid_columnconfigure(0, weight=1)
        self._tile(ter, 0, None, "🩺", "Diagnostics", "Environment checks (coming soon)", False, big=False)

    def _hero(self, parent, row):
        card = ctk.CTkFrame(parent, fg_color=T.BG2, border_color=T.ACCENT, border_width=2,
                            corner_radius=12, width=560, height=132)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text="⚡", font=ctk.CTkFont(size=40), text_color=T.ACCENT_HI)\
            .grid(row=0, column=0, rowspan=2, padx=(28, 18), pady=24)
        ctk.CTkLabel(card, text="Build Image", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=0, column=1, sticky="sw", pady=(28, 0))
        ctk.CTkLabel(card, text="Create new PS5 images — exFAT or FFPFSC", font=T.F["body"],
                     text_color=T.FG3, anchor="w").grid(row=1, column=1, sticky="nw", pady=(0, 28))
        go = ctk.CTkLabel(card, text="Start  →", font=T.F["bodyb"], text_color="#000",
                          fg_color=T.ACCENT, corner_radius=8, padx=18, pady=8)
        go.grid(row=0, column=2, rowspan=2, padx=(0, 28))
        self._bind_click(card, lambda: self.app.enter_mode("build"))

    def _tile(self, parent, col, key, icon, title, desc, enabled, big):
        h = 110 if big else 84
        card = Card(parent, width=272, height=h)
        card.grid(row=0, column=col, padx=8, pady=4, sticky="nsew")
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        ic_color = (T.ACCENT_HI if enabled else T.FG6)
        csize = "title" if big else "body"
        ctk.CTkLabel(card, text=icon, font=T.F[csize], text_color=ic_color)\
            .grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=14)
        ctk.CTkLabel(card, text=title, font=T.F["bodyb"] if big else T.F["body"],
                     text_color=T.FG0 if enabled else T.FG4, anchor="w")\
            .grid(row=0, column=1, sticky="sw", pady=(14, 0) if big else (12, 0))
        ctk.CTkLabel(card, text=desc, font=T.F["meta"], text_color=T.FG5 if enabled else T.FG6,
                     anchor="w").grid(row=1, column=1, sticky="nw", pady=(0, 14))
        if enabled:
            self._bind_click(card, lambda: self.app.enter_mode(key))
        else:
            ctk.CTkLabel(card, text="Soon", font=T.F["meta"], text_color=T.FG6, fg_color=T.BG4,
                         corner_radius=999, padx=8, pady=1)\
                .grid(row=0, column=2, rowspan=2, padx=(0, 14))

    def _bind_click(self, widget, fn):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _e: fn())
        # hover affordance
        widget.bind("<Enter>", lambda _e: widget.configure(fg_color=T.BG3))
        widget.bind("<Leave>", lambda _e: widget.configure(fg_color=T.BG2))
        for child in widget.winfo_children():
            child.configure(cursor="hand2")
            child.bind("<Button-1>", lambda _e: fn())
