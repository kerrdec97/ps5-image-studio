"""Demo mode — a drop-in replacement for BuildWorker that SIMULATES builds.

No subprocess, no lazy_mkpfs, no real files are touched. It emits the exact
same UI events as the real worker so the whole GUI (queue, live progress,
pause/stop, verify-fail → error, history) can be exercised safely.

Enable with:  python run_studio.py --demo   (or env LAZY_STUDIO_DEMO=1)
In demo mode the app also points its config at a throwaway temp dir, so your
real settings / history / queue are never modified.
"""
from __future__ import annotations
import queue
import random
import threading
import time

from .worker import phase_steps

_SHUTDOWN = object()
GB = 1024 ** 3

# Real-looking PS5 titles for fake jobs.
DEMO_SPECS = [
    {"title": "ASTRO BOT", "ppsa": "PPSA01325", "version": "01.007.000", "size": 40 * GB},
    {"title": "Stellar Blade", "ppsa": "PPSA17422", "version": "01.004.000", "size": 92 * GB},
    {"title": "EA SPORTS FC 24", "ppsa": "PPSA07783", "version": "01.012.000", "size": 48 * GB},
    {"title": "Marvel's Spider-Man 2", "ppsa": "PPSA01494", "version": "01.004.000", "size": 98 * GB},
    {"title": "Black Myth: Wukong", "ppsa": "PPSA19891", "version": "01.013.000", "size": 102 * GB},
    {"title": "Tour de France 2024", "ppsa": "PPSA12060", "version": "01.003.000", "size": 24 * GB},
]


class DemoWorker(threading.Thread):
    def __init__(self, event_q: "queue.Queue[dict]"):
        super().__init__(daemon=True)
        self.event_q = event_q
        self.pending: "queue.Queue" = queue.Queue()
        self.jobs_by_id: dict[str, object] = {}
        self._paused = threading.Event()
        self._cancel = threading.Event()
        self._announced = False

    # ── same public API as BuildWorker ────────────────────────
    def submit(self, job):
        self.jobs_by_id[job.id] = job
        self.pending.put(job.id)

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()
        self._emit(type="resumed")

    def is_paused(self):
        return self._paused.is_set()

    def stop_current(self):
        self._cancel.set()

    def shutdown(self):
        self.pending.put(_SHUTDOWN)

    # ── loop ──────────────────────────────────────────────────
    def _emit(self, **kw):
        self.event_q.put(kw)

    def run(self):
        while True:
            while self._paused.is_set():
                if not self._announced:
                    self._emit(type="paused")
                    self._announced = True
                time.sleep(0.2)
            self._announced = False
            try:
                jid = self.pending.get(timeout=0.3)
            except queue.Empty:
                continue
            if jid is _SHUTDOWN:
                break
            job = self.jobs_by_id.get(jid)
            if job is None:
                continue
            self._cancel.clear()
            self._simulate(job)
            if self.pending.empty() and not self._paused.is_set():
                self._emit(type="idle")

    def _simulate(self, job):
        steps = phase_steps(job)
        self._emit(type="job_start", jid=job.id, steps=steps)
        outcome = getattr(job, "demo_outcome", "ok")
        start = time.time()
        gain = random.uniform(36, 47)
        speed = f"{random.randint(380, 520)} MB/s"

        for idx, phase in enumerate(steps):
            self._emit(type="phase", jid=job.id, label=phase, idx=idx, total=len(steps))
            self._emit(type="log", jid=job.id, line=f"… {phase}")
            for k in range(0, 101, 4):
                if self._cancel.is_set():
                    self._emit(type="log", jid=job.id, line="🧹 (demo) discarded staging output")
                    self._emit(type="job_cancelled", jid=job.id)
                    return
                eta = f"{max(0, int((100 - k) / 9))}s"
                self._emit(type="progress", jid=job.id, pct=k / 100, phase=phase,
                           idx=idx, total=len(steps), speed=speed, eta=eta)
                time.sleep(0.04)
            if phase == "Verify" and outcome == "verify_fail":
                self._emit(type="log", jid=job.id, line="❌ (demo) hash mismatch in block 8123")
                self._emit(type="job_error", jid=job.id, error="Verification failed (demo)")
                return

        if outcome == "error":
            self._emit(type="job_error", jid=job.id, error="Simulated build error (demo)")
            return

        unc = job.size_bytes or random.randint(30, 90) * GB
        stored = int(unc * (1 - gain / 100))
        self._emit(type="job_done", jid=job.id, gain=round(gain, 2),
                   elapsed=round(time.time() - start, 2), files=random.randint(900, 2200),
                   uncompressed=unc, stored=stored,
                   final_path=str(job.final_output_path()), verify_ok=True)
