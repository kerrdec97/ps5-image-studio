"""First-run onboarding guidance for PS5 Image Studio.

A non-blocking Toplevel shown once on the very first launch (detected by the
absence of a settings file). Explains the recommended defaults and offers to open
Settings or start the Build Wizard. Marks itself seen via Settings so it never
reappears. UI/settings only — no pipeline contact.
"""
from __future__ import annotations

import customtkinter as ctk

from . import theme as T


# (label, recommendation) lines describing the recommended defaults.
_GUIDANCE = [
    ("Archive folder", "Where finished images are saved. Point this at the drive with room for your library."),
    ("Staging folder", "Temporary space used while building. A fast SSD/NVMe is recommended."),
    ("Verify after build", "Recommended ON for FFPFSC (checks the compressed image). Skipped automatically for exFAT."),
    ("Compression backend / level", "zlib is a safe default. Use ISA-L or another backend only if it's available on your system."),
    ("Filename style", "PPSA + Title + Version is recommended for readable, unambiguous output names."),
    ("Delete source after success", "OFF by default. This permanently deletes the source after a successful build — only enable it if you understand the risk."),
]

_SOURCE_HELP = ("Sources: a dump folder can build to exFAT or FFPFSC; an existing "
                ".exfat or .ffpkg image can be built to FFPFSC. (FFPKG is supported "
                "as input only — it can't be produced as output yet.)")


def show_onboarding(app):
    """Show the first-run guidance over the app. Non-blocking. Writes the
    'seen' flag immediately so it never shows again, even if the user closes it
    with the window control."""
    try:
        win = ctk.CTkToplevel(app)
        win.title("Welcome to PS5 Image Studio")
        win.geometry("680x620")
        win.configure(fg_color=T.BG1)
        win.transient(app)          # stays above the app, but non-modal
        # NOTE: deliberately NOT grab_set() — must be non-blocking.

        # Mark seen right away (and persist), so closing via the X still counts.
        _mark_seen(app)

        wrap = ctk.CTkScrollableFrame(win, fg_color=T.BG1, corner_radius=0,
                                      scrollbar_fg_color=T.BG1,
                                      scrollbar_button_color=T.BG4,
                                      scrollbar_button_hover_color=T.BORDER3)
        wrap.pack(fill="both", expand=True, padx=0, pady=0)
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(wrap, text="👋  Welcome", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=0, column=0, sticky="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(wrap, text="A quick setup before your first build. You can change "
                                "any of this later in Settings.", font=T.F["body"],
                     text_color=T.FG4, anchor="w", wraplength=600, justify="left")\
            .grid(row=1, column=0, sticky="w", padx=24, pady=(0, 16))

        card = ctk.CTkFrame(wrap, fg_color=T.BG2, corner_radius=10)
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="RECOMMENDED DEFAULTS", font=T.F["eyebrow"], text_color=T.FG5,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=18, pady=(15, 8))
        r = 1
        for label, rec in _GUIDANCE:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.grid(row=r, column=0, sticky="ew", padx=18, pady=(0, 8))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, font=T.F["bodyb"], text_color=T.FG1, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=rec, font=T.F["meta"], text_color=T.FG4, anchor="w",
                         wraplength=600, justify="left").grid(row=1, column=0, sticky="w", pady=(1, 0))
            r += 1
        ctk.CTkFrame(card, fg_color="transparent", height=6).grid(row=r, column=0)

        # Source/output explainer
        sc = ctk.CTkFrame(wrap, fg_color=T.BG2, corner_radius=10)
        sc.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 16))
        sc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sc, text="SOURCES & OUTPUTS", font=T.F["eyebrow"], text_color=T.FG5,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=18, pady=(15, 6))
        ctk.CTkLabel(sc, text=_SOURCE_HELP, font=T.F["meta"], text_color=T.FG3, anchor="w",
                     wraplength=600, justify="left").grid(row=1, column=0, sticky="w",
                                                          padx=18, pady=(0, 14))

        # Buttons
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 22))
        btns.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(btns, text="⚙  Open Settings", font=T.F["bodyb"], height=38,
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HI, text_color="#000",
                      command=lambda: _go(win, app, "settings"))\
            .grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(btns, text="⚡  Start Build Wizard", font=T.F["bodyb"], height=38,
                      fg_color=T.BG5, hover_color=T.BORDER3, text_color=T.FG2,
                      command=lambda: _go(win, app, "build"))\
            .grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(btns, text="Don't show again", font=T.F["body"], height=38,
                      fg_color="transparent", hover_color=T.BG3, text_color=T.FG5,
                      command=win.destroy)\
            .grid(row=0, column=3, sticky="e")
    except Exception:
        # Onboarding must never block or crash startup.
        pass


def _go(win, app, key):
    try:
        win.destroy()
    except Exception:
        pass
    try:
        app.enter_mode(key)
    except Exception:
        pass


def _mark_seen(app):
    try:
        app.appstate.settings.first_run_seen = True
        app.appstate.settings.save()
    except Exception:
        pass
