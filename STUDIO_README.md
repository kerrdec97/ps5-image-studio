# Lazy_MkPFS Studio — Handoff Package

A CustomTkinter **PS5 image-building workstation** GUI on top of the `lazy_mkpfs`
runner, built from the verified Claude design. Queue-first (HandBrake /
qBittorrent feel), Windows-first, no Electron, no web UI.

---

## 1. Folder / file tree

```
Lazy_MkPFS-lazy/                  (repo root — already contains lazy_mkpfs/)
├─ run_studio.py                  entry point
├─ requirements-studio.txt        GUI dependency (customtkinter)
├─ STUDIO_README.md               this file
├─ lazy_mkpfs/                    the existing packing/verify library (unchanged)
└─ lazy_studio/                   the GUI
   ├─ __init__.py
   ├─ theme.py                    design tokens (colors/fonts) from the exFAT design system
   ├─ models.py                   Settings, BuildJob, HistoryEntry, AppState + persistence
   ├─ widgets.py                  Card, StatTile, SegBar, Toggle, Stepper, StepDots, LogView…
   ├─ job_runner.py               SUBPROCESS: builds one image, streams JSONL progress events
   ├─ worker.py                   BuildWorker thread: queue, pause, stop, staging-move, verify
   ├─ demo.py                     DemoWorker: simulates builds, touches no real files
   ├─ app.py                      App(ctk.CTk): titlebar + sidebar nav + page swap + event pump
   └─ pages/
      ├─ base.py                  Page base (scrollable frame) + button/entry helpers
      ├─ dashboard.py             KPIs, current build, up-next, quick add
      ├─ queue.py                 running + waiting jobs, queue controls
      ├─ active_build.py          live progress, phase dots, stats, Build Log
      ├─ history.py               completed builds (Open / Rebuild / Log)
      └─ settings.py              compression / performance / SSD staging / integrity
```

Config/state persists to `~/.lazy_mkpfs_studio/` (`settings.json`, `history.json`,
`queue.json`). Demo mode uses a throwaway temp dir instead.

---

## 2. Install / run

```bat
cd Lazy_MkPFS-lazy
python -m pip install -r requirements-studio.txt
python -m pip install zlib-ng isal           :: optional: faster backends
python run_studio.py
```

**Demo mode (no real files, safe to click everything):**

```bat
python run_studio.py --demo
:: or:  set LAZY_STUDIO_DEMO=1  &&  python run_studio.py
```

Run the existing CLI auto-installs `cryptography` on first import.

---

## 3. Module cheat-sheet

| Module | Responsibility |
|---|---|
| `theme.py` | All hex tokens + `init_fonts()`. No `var()`/CSS — Python constants. |
| `models.py` | Dataclasses + `human_size`/`fmt_secs`, title-ID/version parsing, `dir_size`, and JSON persistence for settings, history, **and the queue**. `set_config_dir()` repoints persistence (demo). |
| `widgets.py` | Brand-styled reusable controls. `SegBar` = segmented selector; `Toggle` = CTkSwitch; `Stepper` = −/value/+; `StepDots` = phase dots; `LogView` = colored Build Log. |
| `job_runner.py` | Child process. Runs `pack_folder`/`pack_file`, captures their stderr progress bar + verbose lines, re-emits as JSONL events. Returns final `BuildStats` as a `result` event. |
| `worker.py` | `BuildWorker` thread. Sequential queue; spawns the job subprocess; **Stop** = terminate + delete partial; **build → verify(staging) → move**; in-thread `verify_pfs`. |
| `demo.py` | `DemoWorker` with the same API; simulates phases/progress/verify-fail; no subprocess, no disk writes. `DEMO_SPECS` = fake PS5 titles. |
| `app.py` | The window. Sidebar nav with `tkraise()` page swap, storage meters, 100 ms `_pump()` that drains worker events on the main thread, full job lifecycle, demo seeding. |
| `pages/*` | One file per screen; each a `CTkScrollableFrame` with `build()` + `refresh()`. |

**Threading rule:** widgets are touched only on the Tk main thread. Workers and
the folder-size scan communicate exclusively through the event queue (drained in
`_pump`) — there are no `widget` calls off-thread.

---

## 4. Known v1 limitations (by design)

- **Concurrent jobs > 1** is shown in Settings but the v1 worker runs **one job at
  a time**. Real parallelism needs disk/RAM guards — deferred on purpose.
- **Stop** is a process `terminate()` between phases/files, then the partial
  staging file is deleted. It is not a graceful in-library flush (the runner has
  no cancel token).
- **Pause** takes effect *after* the current job; it does not freeze a running
  build.
- Per-file counts aren't exposed by the library, so the Active Build "Files" tile
  is intentionally omitted; **Gain** fills in on completion.
- History's **Open** assumes the archive path still exists on disk.

---

## 5. Windows testing checklist

Demo mode first (safe), then one small real build.

**Demo (`python run_studio.py --demo`):**
- [ ] App launches; titlebar shows the amber **DEMO** pill.
- [ ] Click every sidebar item — all 6 pages render, only one visible.
- [ ] Queue shows 2 seeded jobs; History shows 2 seeded entries.
- [ ] **Start All** → first job animates phases on Active Build; Build Log scrolls.
- [ ] **🧪 Add demo job** adds more; they queue behind the running one (Concurrent jobs = 1).
- [ ] **Pause** → running job finishes, next one does not start; **Resume** continues.
- [ ] **Stop build** mid-run → job goes *cancelled*, log shows "discarded staging".
- [ ] The seeded **verify-fail** job ends as **error** (red), not done, and is NOT added to History.
- [ ] Completed demo job appears in **History**; **Rebuild** re-queues it.
- [ ] Change a **Setting** (e.g. level 3→5), close, relaunch `--demo`… (note: demo wipes its temp config each launch — use a real run to confirm persistence).

**Real persistence (normal launch):**
- [ ] Settings: change backend/level/workers/toggles → close → reopen → values stuck.
- [ ] Add a job, **don't** start it → close → reopen → job still in Queue.

**Real build (see §7 for the safe first one):**
- [ ] Add a small dump folder → **Add & Start** → progress advances, Build Log streams.
- [ ] On success the image lands in the **archive** folder and a **History** row appears.
- [ ] With SSD staging on, confirm the file is built in **staging** then moved to **archive**.
- [ ] Toggle Verify on and point at a deliberately truncated image → job ends **error**, archive untouched.
- [ ] Stop a real build mid-run → partial staging file is gone; archive untouched.

---

## 6. Where live CTk testing may still reveal issues

I authored this without a Python/display environment, so these are the most
likely (all small) fixes:

- **CTkLabel kwargs across versions.** `padx/pady/wraplength/justify/anchor` are
  valid passthroughs in current CustomTkinter; a much older version could reject
  one. Fix = wrap the label in a frame.
- **`grid(in_=…)` in `settings.py`.** Controls are created on the card and gridded
  into a child row frame. Valid per Tk rules; if your version is fussy, create the
  control with the row frame as master instead.
- **`CTkTextbox` tag colors.** `LogView` uses `self._textbox.tag_config(...)`. If a
  version renames the internal handle, switch to the public tag API.
- **Emoji glyphs** (▦ ▤ ⚡ 🎮) render via Segoe UI Emoji on Windows — fine; on a
  stripped VM a couple may show as boxes (cosmetic).
- **High-DPI scaling** — if text looks huge/tiny, set
  `ctk.set_widget_scaling(0.9)` in `app.py`.
- **Disk meters** call `shutil.disk_usage` on the staging/archive paths; if a path
  is an unmounted drive it falls back to "n/a" (handled, but verify).

None of these affect logic — they're rendering quibbles, each a one-liner.

---

## 7. Safest first REAL test

Don't start on a 100 GB title. Do this:

1. Launch normally: `python run_studio.py`.
2. **Settings:** Backend = `zlib` (no extra deps), Level = `3`, Compression
   workers = `Auto`, **Concurrent jobs = 1**, Verify = **on**.
3. **SSD staging:** point *Staging drive* and *Archive folder* at two folders on a
   drive with plenty of free space, e.g.
   - Staging: `D:\Stage`
   - Archive: `D:\PS5\Images`
   (Create both folders first.)
4. **Add Build Job → Dump folder**, Browse to a **small** real dump (a 3–15 GB
   game is ideal for the first run), confirm the detected PPSA/Title/Size.
5. **Add & Start Now.** Watch Active Build: Scan → Create exFAT → Compress →
   Verify → Move. On success the `.ffpfsc` is in `D:\PS5\Images` and a History row
   appears.
6. Once that round-trips cleanly, scale up to the big titles and longer overnight
   queues.

> Tip: leave Verify **on** for the first real builds — it gates the archive move,
> so a bad image can never silently land in your library.
