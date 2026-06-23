"""Base page: a scrollable content frame with on_show()/refresh() hooks."""
from __future__ import annotations
import customtkinter as ctk
from .. import theme as T


class Page(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        # Theme the scrollbar too — CTkScrollableFrame otherwise falls back to the
        # default CTk grays for its scrollbar chrome, which reads as a "legacy"
        # background against the dark theme.
        super().__init__(master, fg_color=T.BG1, corner_radius=0,
                         scrollbar_fg_color=T.BG1, scrollbar_button_color=T.BG4,
                         scrollbar_button_hover_color=T.BORDER3)
        self.app = app
        self.state = app.appstate
        self._page_key = "?"
        self.grid_columnconfigure(0, weight=1)
        self.build()

    def build(self) -> None:  # override
        ...

    def on_show(self) -> None:  # override
        self.refresh()

    def refresh(self) -> None:  # override
        ...


def primary_btn(master, text, command, color=T.ACCENT, text_color="#000000", **kw):
    kw.setdefault("height", 36)
    return ctk.CTkButton(master, text=text, command=command, font=T.F["bodyb"],
                         fg_color=color, hover_color=T.ACCENT_HI if color == T.ACCENT else color,
                         text_color=text_color, corner_radius=5, **kw)


def ghost_btn(master, text, command, text_color=T.FG2, **kw):
    kw.setdefault("height", 36)
    return ctk.CTkButton(master, text=text, command=command, font=T.F["bodyb"],
                         fg_color=T.BG5, hover_color=T.BORDER3, text_color=text_color,
                         border_color=T.BORDER3, border_width=1, corner_radius=5, **kw)


def home_btn_large(master, app, **kw):
    """Prominent top-left '🏠 Home' navigation button. After the mode-based UI
    migration, Home is the primary navigation control (launcher + escape hatch),
    so it gets an accent-tinted, clearly-tappable button — not the easy-to-miss
    titlebar control. Used at the top-left of every workspace page."""
    kw.setdefault("height", 34)
    kw.setdefault("width", 110)
    return ctk.CTkButton(master, text="🏠  Home", command=app.go_home, font=T.F["bodyb"],
                         fg_color=T.ACCENT, hover_color=T.ACCENT_HI, text_color="#000000",
                         corner_radius=6, **kw)


def field_entry(master, value="", width=0):
    e = ctk.CTkEntry(master, font=T.F["mono"], fg_color=T.FIELD_BG, text_color=T.FIELD_FG,
                     border_width=0, corner_radius=4, height=36)
    if width:
        e.configure(width=width)
    if value:
        e.insert(0, value)
    return e
