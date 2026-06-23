"""Design tokens lifted verbatim from the verified PS5 Image Studio mock
(exFAT Image Builder design system). Colors are hard-coded hex; fonts are
created once the Tk root exists via init_fonts()."""
from __future__ import annotations
import customtkinter as ctk

# ── Backgrounds (pitch-black → elevated card) ──
BG0 = "#050505"   # sunken console / build log
BG1 = "#0a0a0a"   # page canvas
BG2 = "#111111"   # card / panel
BG3 = "#141414"   # queue row / list item
BG4 = "#1a1a1a"   # titlebar / hover / active nav
BG5 = "#1e1e1e"   # progress track / sunken input
SIDEBAR = "#070707"

# ── Borders (hairline, dark) ──
BORDER1 = "#1a1a1a"
BORDER2 = "#222222"
BORDER3 = "#2a2a2a"
BORDER4 = "#333333"

# ── Foregrounds ──
FG0 = "#ffffff"
FG1 = "#e0e0e0"
FG2 = "#cccccc"
FG3 = "#aaaaaa"
FG4 = "#888888"
FG5 = "#666666"
FG6 = "#555555"

# ── Accent (electric blue) ──
ACCENT = "#4a9eff"
ACCENT_HI = "#7ec8ff"
INFO_BG = "#0d1f33"

# ── Status (traffic lights) ──
SUCCESS = "#4caf50"
SUCCESS_HI = "#81c784"
SUCCESS_BG = "#0a1f0a"
WARN = "#ffaa00"
WARN_HI = "#ffcc44"
WARN_BG = "#1a1200"
DANGER = "#f44336"
DANGER_HI = "#ff4444"
DANGER_BG = "#1f0a0a"
PURPLE = "#9b59b6"

# ── Shared status styling (single source of truth) ──
# Used by the Active Build badge and the Queue row dots/pills so a status looks
# identical everywhere. fg = dot/border/accent, text = pill text colour,
# bg = pill background, label = pill text.
#   running = amber · done = green · error = red (FAILED) · paused = blue ·
#   waiting / cancelled / idle = grey
STATUS_STYLE: dict[str, dict[str, str]] = {
    "running":   {"fg": WARN,    "text": WARN_HI,    "bg": WARN_BG,    "label": "RUNNING"},
    "done":      {"fg": SUCCESS, "text": SUCCESS_HI, "bg": SUCCESS_BG, "label": "DONE"},
    "error":     {"fg": DANGER,  "text": DANGER_HI,  "bg": DANGER_BG,  "label": "FAILED"},
    "paused":    {"fg": ACCENT,  "text": ACCENT_HI,  "bg": INFO_BG,    "label": "PAUSED"},
    "waiting":   {"fg": BORDER4, "text": FG4, "bg": BG4, "label": "WAITING"},
    "cancelled": {"fg": BORDER4, "text": FG4, "bg": BG4, "label": "CANCELLED"},
    "idle":      {"fg": BORDER4, "text": FG4, "bg": BG4, "label": "IDLE"},
}


def status_style(status: str) -> dict[str, str]:
    """Look up the style for a job status, falling back to the grey idle style."""
    return STATUS_STYLE.get(status, STATUS_STYLE["idle"])

# ── Build-log terminal colors ──
TERM_GREEN = "#00ff41"
TERM_RED = "#ff4444"

# ── Light form fields (Windows-form holdover) ──
FIELD_BG = "#f0f0f0"
FIELD_FG = "#111111"

FONT_SANS = "Segoe UI"
FONT_MONO = "Consolas"

# Populated by init_fonts(); access via theme.F["body"], etc.
F: dict[str, ctk.CTkFont] = {}


def init_fonts() -> None:
    """Create CTkFont objects. Must be called after the Tk root is created."""
    F.update({
        "h1":      ctk.CTkFont(FONT_SANS, 24, "bold"),
        "h2":      ctk.CTkFont(FONT_SANS, 19, "bold"),
        "title":   ctk.CTkFont(FONT_SANS, 14, "bold"),
        "body":    ctk.CTkFont(FONT_SANS, 13),
        "bodyb":   ctk.CTkFont(FONT_SANS, 13, "bold"),
        "label":   ctk.CTkFont(FONT_SANS, 12),
        "meta":    ctk.CTkFont(FONT_SANS, 11),
        "eyebrow": ctk.CTkFont(FONT_SANS, 11, "bold"),
        "stat":    ctk.CTkFont(FONT_MONO, 24, "bold"),
        "statlg":  ctk.CTkFont(FONT_MONO, 18, "bold"),
        "mono":    ctk.CTkFont(FONT_MONO, 12),
        "monob":   ctk.CTkFont(FONT_MONO, 12, "bold"),
        "monosm":  ctk.CTkFont(FONT_MONO, 11),
        "nav":     ctk.CTkFont(FONT_SANS, 13),
        "navb":    ctk.CTkFont(FONT_SANS, 13, "bold"),
        "icon":    ctk.CTkFont(FONT_SANS, 14),
    })
