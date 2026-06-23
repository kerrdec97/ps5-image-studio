"""Reusable CustomTkinter widgets styled to the exFAT Image Builder system."""
from __future__ import annotations
import customtkinter as ctk
from . import theme as T


class Card(ctk.CTkFrame):
    """A #111 panel with hairline border."""
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", T.BG2)
        kw.setdefault("border_color", T.BORDER2)
        kw.setdefault("border_width", 1)
        kw.setdefault("corner_radius", 8)
        super().__init__(master, **kw)


def eyebrow(master, text):
    return ctk.CTkLabel(master, text=text.upper(), font=T.F["eyebrow"], text_color=T.FG5)


def label(master, text, color=T.FG4, font_key="label"):
    return ctk.CTkLabel(master, text=text, font=T.F[font_key], text_color=color)


class StatTile(Card):
    def __init__(self, master, title, value, sub="", value_color=T.FG0):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title.upper(), font=T.F["meta"], text_color=T.FG5,
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        self.value = ctk.CTkLabel(self, text=value, font=T.F["stat"], text_color=value_color, anchor="w")
        self.value.grid(row=1, column=0, sticky="ew", padx=16)
        self.sub = ctk.CTkLabel(self, text=sub, font=T.F["meta"], text_color=T.FG6, anchor="w")
        self.sub.grid(row=2, column=0, sticky="ew", padx=16, pady=(2, 14))

    def set(self, value=None, sub=None, value_color=None):
        if value is not None:
            self.value.configure(text=value)
        if sub is not None:
            self.sub.configure(text=sub)
        if value_color is not None:
            self.value.configure(text_color=value_color)


class SegBar(ctk.CTkFrame):
    """Row of segmented buttons (backend / level / workers). Full color control."""
    def __init__(self, master, options, values=None, default=None, command=None,
                 min_w=0, font_key="bodyb"):
        super().__init__(master, fg_color="transparent")
        self.options = list(options)
        self.values = list(values) if values else list(options)
        self.command = command
        self.font_key = font_key
        self.min_w = min_w
        self._value = default if default is not None else self.values[0]
        self.buttons: dict = {}
        for i, (lab, val) in enumerate(zip(self.options, self.values)):
            b = ctk.CTkButton(self, text=str(lab), font=T.F[font_key], width=min_w, height=34,
                              corner_radius=6, border_width=1,
                              command=lambda v=val: self._on(v))
            b.grid(row=0, column=i, padx=(0 if i == 0 else 6, 0))
            self.buttons[val] = b
        self._restyle()

    def _on(self, val):
        self._value = val
        self._restyle()
        if self.command:
            self.command(val)

    def _restyle(self):
        for val, b in self.buttons.items():
            active = val == self._value
            b.configure(
                fg_color=T.ACCENT if active else T.BG4,
                hover_color=T.ACCENT_HI if active else T.BORDER3,
                text_color="#000000" if active else T.FG3,
                border_color=T.ACCENT if active else T.BORDER2,
            )

    def get(self):
        return self._value

    def set(self, val):
        if val in self.buttons:
            self._value = val
            self._restyle()


class Toggle(ctk.CTkSwitch):
    def __init__(self, master, value=False, command=None):
        self._cb = command
        super().__init__(master, text="", width=46, switch_width=44, switch_height=24,
                         progress_color=T.ACCENT, fg_color=T.BORDER4, button_color="#ffffff",
                         button_hover_color="#f0f0f0", command=self._on)
        if value:
            self.select()
        else:
            self.deselect()

    def _on(self):
        if self._cb:
            self._cb(bool(self.get()))


class Stepper(ctk.CTkFrame):
    """- value + integer stepper."""
    def __init__(self, master, value=1, lo=1, hi=4, command=None):
        super().__init__(master, fg_color=T.BG4, border_color=T.BORDER3, border_width=1, corner_radius=5)
        self.value, self.lo, self.hi, self.command = value, lo, hi, command
        ctk.CTkButton(self, text="−", width=36, height=32, corner_radius=0, fg_color=T.BG4,
                      hover_color=T.BORDER3, text_color=T.FG3, font=T.F["title"],
                      command=lambda: self._bump(-1)).grid(row=0, column=0)
        self.lbl = ctk.CTkLabel(self, text=str(value), width=46, font=T.F["monob"], text_color=T.FG0)
        self.lbl.grid(row=0, column=1)
        ctk.CTkButton(self, text="+", width=36, height=32, corner_radius=0, fg_color=T.BG4,
                      hover_color=T.BORDER3, text_color=T.FG3, font=T.F["title"],
                      command=lambda: self._bump(1)).grid(row=0, column=2)

    def _bump(self, d):
        self.value = max(self.lo, min(self.hi, self.value + d))
        self.lbl.configure(text=str(self.value))
        if self.command:
            self.command(self.value)

    def get(self):
        return self.value


class StepDots(ctk.CTkFrame):
    """Row of labelled phase dots."""
    def __init__(self, master, steps):
        super().__init__(master, fg_color="transparent")
        self.dots, self.labels = [], []
        self.build(steps)

    def build(self, steps):
        for w in self.dots + self.labels:
            w.destroy()
        self.dots, self.labels = [], []
        for i, s in enumerate(steps):
            self.grid_columnconfigure(i, weight=1)
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.grid(row=0, column=i, sticky="ew")
            dot = ctk.CTkFrame(holder, width=12, height=12, corner_radius=6, fg_color=T.BORDER4)
            dot.pack()
            dot.pack_propagate(False)
            lab = ctk.CTkLabel(holder, text=s, font=T.F["meta"], text_color=T.FG6)
            lab.pack(pady=(6, 0))
            self.dots.append(dot)
            self.labels.append(lab)

    def set_active(self, idx):
        for i, (dot, lab) in enumerate(zip(self.dots, self.labels)):
            if i < idx:
                dot.configure(fg_color=T.SUCCESS)
                lab.configure(text_color=T.SUCCESS_HI)
            elif i == idx:
                dot.configure(fg_color=T.ACCENT)
                lab.configure(text_color=T.ACCENT)
            else:
                dot.configure(fg_color=T.BORDER4)
                lab.configure(text_color=T.FG6)

    def set_done(self):
        for dot, lab in zip(self.dots, self.labels):
            dot.configure(fg_color=T.SUCCESS)
            lab.configure(text_color=T.SUCCESS_HI)


def pill(master, text, fg, bg, border):
    return ctk.CTkLabel(master, text=text, font=T.F["meta"], text_color=fg,
                        fg_color=bg, corner_radius=999, padx=11, pady=3)


class StatusDot(ctk.CTkFrame):
    COLORS = {"waiting": T.BORDER4, "paused": T.WARN, "running": T.ACCENT,
              "done": T.SUCCESS, "error": T.DANGER, "cancelled": T.FG5}

    def __init__(self, master, status="waiting"):
        super().__init__(master, width=12, height=12, corner_radius=6,
                         fg_color=self.COLORS.get(status, T.BORDER4))
        self.pack_propagate(False)

    def set_status(self, status):
        self.configure(fg_color=self.COLORS.get(status, T.BORDER4))


class LogView(ctk.CTkTextbox):
    """Build Log console with terminal colors."""
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", T.BG0)
        kw.setdefault("border_color", T.BORDER1)
        kw.setdefault("border_width", 1)
        kw.setdefault("corner_radius", 8)
        kw.setdefault("font", T.F["mono"])
        kw.setdefault("text_color", T.FG3)
        super().__init__(master, **kw)
        tb = self._textbox
        tb.tag_config("ok", foreground=T.TERM_GREEN)
        tb.tag_config("err", foreground=T.TERM_RED)
        tb.tag_config("accent", foreground=T.ACCENT)
        tb.tag_config("muted", foreground=T.FG6)
        self.configure(state="disabled")

    def add(self, text):
        tag = None
        if text.startswith(("✅",)) or "passed" in text.lower() or "successfully" in text.lower():
            tag = "ok"
        elif text.startswith(("❌", "⚠️")) or "error" in text.lower() or "fail" in text.lower():
            tag = "err"
        elif text.startswith(("$", "🛡️", "📦")) or "compress" in text.lower():
            tag = "accent"
        elif text.startswith(("🧹", "🔍")):
            tag = "muted"
        self.configure(state="normal")
        self._textbox.insert("end", text + "\n", (tag,) if tag else ())
        self.see("end")
        self.configure(state="disabled")

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")
