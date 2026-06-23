"""History: completed builds with Open / Rebuild / Log actions."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
import customtkinter as ctk
from .. import theme as T
from .. import models as M
from ..widgets import Card
from .base import Page, ghost_btn, home_btn_large


def _open_in_explorer(path: str):
    p = Path(path)
    folder = p.parent if p.is_file() or p.suffix else p
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # noqa: SLF001
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception:
        pass


def _open_file(path: str) -> bool:
    """Open a FILE itself (not its parent folder) in the OS default app. Returns
    True if the file exists and an open was attempted, False otherwise — so callers
    can fall back to an in-app popup when there's no saved file."""
    try:
        p = Path(path)
        if not path or not p.is_file():
            return False
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # noqa: SLF001
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:
        return False


class HistoryPage(Page):
    def build(self):
        self._filter = "all"   # all | exfat | ffpfsc | success | failed
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 12))
        head.grid_columnconfigure(0, weight=1)
        home_btn_large(head, self.app).grid(row=0, column=0, sticky="w", pady=(0, 10))
        ctk.CTkLabel(head, text="History", font=T.F["h1"], text_color=T.FG0, anchor="w")\
            .grid(row=1, column=0, sticky="w")
        self.sub = ctk.CTkLabel(head, text="", font=T.F["body"], text_color=T.FG5, anchor="w")
        self.sub.grid(row=2, column=0, sticky="w", pady=(2, 0))
        ghost_btn(head, "🧹  Clear History", self._clear, height=34).grid(row=1, column=1, rowspan=2, sticky="e")

        # Stats strip (compact KPI tiles), between the header and the filters.
        self.stats_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_holder.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 12))
        self.stats_holder.grid_columnconfigure(0, weight=1)

        # Filter bar
        fbar = ctk.CTkFrame(self, fg_color="transparent")
        fbar.grid(row=2, column=0, sticky="w", padx=30, pady=(0, 12))
        self._filter_btns = {}
        for i, (key, label) in enumerate([("all", "All"), ("exfat", "exFAT"), ("ffpfsc", "FFPFSC"),
                                          ("success", "Success"), ("failed", "Failed")]):
            b = ctk.CTkButton(fbar, text=label, font=T.F["meta"], height=28, width=10,
                              corner_radius=999, command=lambda k=key: self._set_filter(k))
            b.grid(row=0, column=i, padx=(0, 6))
            self._filter_btns[key] = b

        self.card = Card(self)
        self.card.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 30))
        self.card.grid_columnconfigure(0, weight=1)

    def _set_filter(self, key):
        self._filter = key
        self.refresh()

    def _apply_filter(self, hist):
        f = self._filter
        if f == "all":
            return hist
        out = []
        for h in hist:
            outcome = getattr(h, "outcome", "done") or "done"
            ext = (getattr(h, "out_ext", "") or "").lower()
            if f == "exfat" and ext == ".exfat":
                out.append(h)
            elif f == "ffpfsc" and ext in (".ffpfsc", ".ffpfs"):
                out.append(h)
            elif f == "success" and outcome == "done":
                out.append(h)
            elif f == "failed" and outcome in ("error", "cancelled"):
                out.append(h)
        return out

    # ── stats strip ───────────────────────────────────────────
    _UNIT = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

    @staticmethod
    def _parse_size(token: str):
        """Parse a single human_size token ('37.2 GB', '512 MB') to bytes, or None
        if it doesn't match. Matches human_size's '<num> <UNIT>' output exactly."""
        import re
        m = re.fullmatch(r"\s*([\d.]+)\s*(B|KB|MB|GB|TB)\s*", token or "")
        if not m:
            return None
        try:
            return float(m.group(1)) * HistoryPage._UNIT[m.group(2)]
        except (ValueError, KeyError):
            return None

    def _history_stats(self, hist):
        """Derive summary stats from existing HistoryEntry fields. Strict + fails
        closed: unparseable gain/sizes rows are skipped, never guessed."""
        total = len(hist)
        success = sum(1 for h in hist if getattr(h, "outcome", "done") == "done")
        failed = sum(1 for h in hist if getattr(h, "outcome", "done") in ("error", "cancelled"))

        # Average gain: parse "46.8%" -> 46.8, skip "—"/"-"/blank/non-numeric.
        gains = []
        for h in hist:
            g = (getattr(h, "gain", "") or "").strip().rstrip("%").strip()
            if g and g not in ("—", "-"):
                try:
                    gains.append(float(g))
                except ValueError:
                    pass
        avg_gain = (sum(gains) / len(gains)) if gains else None

        # Total space saved: only rows with a strict "X UNIT → Y UNIT" sizes string.
        # exFAT ("3.4 GB exFAT image"), partial ("X → —") and "—" are skipped.
        saved_bytes = 0
        saved_any = False
        for h in hist:
            s = getattr(h, "sizes", "") or ""
            if "→" not in s:
                continue
            before_t, after_t = (p.strip() for p in s.split("→", 1))
            before, after = self._parse_size(before_t), self._parse_size(after_t)
            if before is None or after is None:
                continue
            diff = before - after
            if diff > 0:
                saved_bytes += diff
                saved_any = True

        # Most recent result (history is newest-first).
        recent = None
        if hist:
            h0 = hist[0]
            recent = (getattr(h0, "outcome", "done"), getattr(h0, "name", "") or "—")

        return {
            "total": total, "success": success, "failed": failed,
            "avg_gain": avg_gain, "saved_bytes": saved_bytes if saved_any else None,
            "recent": recent,
        }

    def _build_stats(self, hist):
        for w in self.stats_holder.winfo_children():
            w.destroy()
        st = self._history_stats(hist)

        # Build the tile list. Space-saved is included only if available.
        tiles = [
            ("📦", "Total Builds", str(st["total"]), T.FG1),
            ("✅", "Successful", str(st["success"]), T.SUCCESS),
            ("⚠", "Failed / Cancelled", str(st["failed"]),
             T.WARN_HI if st["failed"] else T.FG4),
            ("📈", "Average Gain",
             f"{st['avg_gain']:.1f}%" if st["avg_gain"] is not None else "—", T.ACCENT_HI),
        ]
        if st["saved_bytes"] is not None:
            tiles.append(("💾", "Space Saved", M.human_size(st["saved_bytes"]), T.SUCCESS))
        if st["recent"] is not None:
            outcome, name = st["recent"]
            glyph = {"done": "✅", "error": "❌", "cancelled": "⏹"}.get(outcome, "✅")
            short = name if len(name) <= 22 else name[:21] + "…"
            tiles.append(("🕓", "Most Recent", f"{glyph} {short}", T.FG2))

        strip = ctk.CTkFrame(self.stats_holder, fg_color="transparent")
        strip.grid(row=0, column=0, sticky="ew")
        for i in range(len(tiles)):
            strip.grid_columnconfigure(i, weight=1, uniform="hstat")
        for i, (icon, label, value, color) in enumerate(tiles):
            t = ctk.CTkFrame(strip, fg_color=T.BG3, corner_radius=7)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            t.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(t, text=f"{icon}  {label}", font=T.F["meta"], text_color=T.FG5,
                         anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(t, text=value, font=T.F["monob"], text_color=color, anchor="w")\
                .grid(row=1, column=0, sticky="w", padx=12, pady=(2, 11))

    def refresh(self):
        for w in self.card.winfo_children():
            w.destroy()
        all_hist = self.state.history
        self._build_stats(all_hist)   # stats summarize full history, not the filter
        # highlight the active filter button
        for k, b in getattr(self, "_filter_btns", {}).items():
            active = (k == self._filter)
            b.configure(fg_color=T.ACCENT if active else T.BG5,
                        text_color="#000" if active else T.FG3)
        hist = self._apply_filter(all_hist)
        if all_hist:
            gains = []
            for h in hist:
                g = (h.gain or "").strip("%").strip()
                try:
                    gains.append(float(g))
                except (TypeError, ValueError):
                    pass  # failed/cancelled rows have no numeric gain
            shown = f"{len(hist)} of {len(all_hist)}" if self._filter != "all" else f"{len(all_hist)}"
            if gains:
                self.sub.configure(text=f"{shown} builds · avg {sum(gains)/len(gains):.1f}% gain")
            else:
                self.sub.configure(text=f"{shown} builds")
        else:
            self.sub.configure(text="No completed builds yet.")

        # Empty-state: when there are no rows to show, render a proper empty-state
        # card (icon + message + CTA) INSTEAD of the table header + a lone centered
        # label in a tall card. Two distinct cases: history truly empty vs. a filter
        # hiding everything.
        if not hist:
            self._render_empty(bool(all_hist))
            return

        hdr = ctk.CTkFrame(self.card, fg_color=T.BG4, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        cols = [("Image", 0, "w"), ("Raw → Stored", 130, "w"), ("Gain", 64, "e"),
                ("Time", 80, "e"), ("Backend", 95, "w"), ("Actions", 200, "e")]
        for i, (txt, w, anc) in enumerate(cols):
            hdr.grid_columnconfigure(i, weight=1 if i == 0 else 0)
            ctk.CTkLabel(hdr, text=txt.upper(), font=T.F["meta"], text_color=T.FG4, width=w,
                         anchor=anc).grid(row=0, column=i, sticky="ew", padx=(18, 8), pady=11)

        for r, h in enumerate(hist, start=1):
            outcome = getattr(h, "outcome", "done") or "done"
            icon = {"done": "✅", "error": "❌", "cancelled": "⏹"}.get(outcome, "✅")
            ostyle = T.status_style({"done": "done", "error": "error",
                                     "cancelled": "cancelled"}.get(outcome, "done"))
            gain_color = ostyle["text"] if outcome != "done" else T.SUCCESS_HI
            row = ctk.CTkFrame(self.card, fg_color="transparent")
            row.grid(row=r, column=0, sticky="ew")
            row.grid_columnconfigure(0, weight=1)
            name = ctk.CTkFrame(row, fg_color="transparent")
            name.grid(row=0, column=0, sticky="w", padx=18, pady=11)
            ctk.CTkLabel(name, text=f"{icon}  {h.name}", font=T.F["bodyb"], text_color=T.FG0, anchor="w")\
                .grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(name, text=f"{h.ppsa} · {h.out_ext} · {h.when}", font=T.F["monosm"],
                         text_color=T.FG5, anchor="w").grid(row=1, column=0, sticky="w")
            ctk.CTkLabel(row, text=h.sizes, font=T.F["mono"], text_color=T.FG3, width=130, anchor="w")\
                .grid(row=0, column=1, padx=8)
            ctk.CTkLabel(row, text=h.gain, font=T.F["monob"], text_color=gain_color, width=64,
                         anchor="e").grid(row=0, column=2, padx=8)
            ctk.CTkLabel(row, text=h.time, font=T.F["mono"], text_color=T.FG4, width=80, anchor="e")\
                .grid(row=0, column=3, padx=8)
            ctk.CTkLabel(row, text=h.backend, font=T.F["monosm"], text_color=T.FG4, width=95, anchor="w")\
                .grid(row=0, column=4, padx=8)
            act = ctk.CTkFrame(row, fg_color="transparent")
            act.grid(row=0, column=5, padx=(8, 18))
            for txt, cmd in [("📂 Open", lambda p=h.final_path: _open_in_explorer(p)),
                             ("🔄 Rebuild", lambda e=h: self._rebuild(e)),
                             ("📋 Log", lambda e=h: self._show_log(e))]:
                ctk.CTkButton(act, text=txt, font=T.F["meta"], fg_color=T.BG5, hover_color=T.BORDER3,
                              text_color=T.FG3, height=28, width=10, corner_radius=4,
                              command=cmd).pack(side="left", padx=3)
            ctk.CTkFrame(self.card, fg_color=T.BORDER1, height=1).grid(row=r, column=0, sticky="sew")

    def _render_empty(self, has_history):
        """Proper empty-state inside the results card. Two cases:
          • has_history=False → history is genuinely empty ("No history yet")
          • has_history=True  → a filter is hiding every row ("No results …")
        A New Build CTA is always offered; a Clear-filter CTA is added only when a
        filter is active. Filters and Clear History remain intact (unchanged)."""
        box = ctk.CTkFrame(self.card, fg_color="transparent")
        box.grid(row=0, column=0, sticky="ew", padx=20, pady=(28, 28))
        box.grid_columnconfigure(0, weight=1)
        if has_history:
            icon, title = "🔍", "No results for this filter"
            sub = "No builds match the current filter. Clear it to see everything."
        else:
            icon, title = "🗂️", "No history yet"
            sub = "Completed builds will appear here. Start your first build to begin."
        ctk.CTkLabel(box, text=icon, font=T.F["h1"], text_color=T.FG5)\
            .grid(row=0, column=0, pady=(0, 6))
        ctk.CTkLabel(box, text=title, font=T.F["h2"], text_color=T.FG2)\
            .grid(row=1, column=0, pady=(0, 2))
        ctk.CTkLabel(box, text=sub, font=T.F["body"], text_color=T.FG5,
                     justify="center", wraplength=520).grid(row=2, column=0, pady=(0, 16))
        cta = ctk.CTkFrame(box, fg_color="transparent")
        cta.grid(row=3, column=0)
        from .base import primary_btn
        primary_btn(cta, "⚡  New Build", lambda: self.app.enter_mode("build"))\
            .grid(row=0, column=0, padx=4)
        if has_history:
            ghost_btn(cta, "✕  Clear filter", lambda: self._set_filter("all"))\
                .grid(row=0, column=1, padx=4)

    def _rebuild(self, h):
        self.app.add_job_from_path(h.src_path, src_type=h.src_type)
        self.app.show_page("queue")

    def _show_log(self, h):
        # Prefer the saved .txt log on disk when one was written; otherwise fall
        # back to the in-app popup built from the captured log lines.
        if _open_file(getattr(h, "log_path", "")):
            return
        win = ctk.CTkToplevel(self)
        win.title(f"Build log — {h.name}")
        win.geometry("760x520")
        win.configure(fg_color=T.BG1)
        from ..widgets import LogView
        lv = LogView(win)
        lv.pack(fill="both", expand=True, padx=12, pady=12)
        for ln in (h.log or ["(no log captured)"]):
            lv.add(ln)

    def _clear(self):
        self.state.history.clear()
        from .. import models as M
        M.save_history(self.state.history)
        self.refresh()
