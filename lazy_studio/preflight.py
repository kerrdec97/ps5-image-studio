"""Preflight space estimation for the Build Wizard.

Pure, read-only logic: estimates per-job temporary and final space, aggregates a
multi-build queue per storage volume, and returns pass/warn/block status against
free space. No UI, no worker, no build-pipeline changes.

Key honesty rules (see the preflight audit):
  * exFAT image size is EXACT (calculate_exfat_size models full overhead).
  * compressed .ffpfsc size is UNKNOWABLE pre-build, so it is estimated
    conservatively as "no compression" (final ~= input image size).
  * dump -> ffpfsc peak = temp exFAT (exact) + estimated final output (both
    coexist before the temp is deleted).
  * exfat/ffpkg source -> ffpfsc peak = source size + estimated final output.
  * builds are sequential, so a multi-build queue needs: archive = SUM of final
    outputs; staging = LARGEST single build peak.
  * BLOCK only when an EXACT requirement exceeds free space; WARN when only the
    conservative ESTIMATE exceeds it (a real compressing build might still fit).
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Read-only use of the exact exFAT sizing model. Never modifies create_exfat.
try:
    from lazy_mkpfs.create_exfat import calculate_exfat_size
except Exception:  # pragma: no cover - lets the module import even if unavailable
    calculate_exfat_size = None

# Conservative safety margin applied on top of every requirement.
SAFETY_FRACTION = 0.10            # +10%
SAFETY_FIXED = 256 * 1024 * 1024  # and at least +256 MB headroom

PASS, WARN, BLOCK = "pass", "warn", "block"


def _with_margin(n: int) -> int:
    return int(n + max(n * SAFETY_FRACTION, SAFETY_FIXED))


def _volume_id(path: Path):
    """Best-effort identity of the storage volume a path lives on. Uses st_dev
    (cross-platform) on the nearest existing ancestor; falls back to the path
    anchor string. If identity can't be determined, returns a unique object so
    callers treat volumes as DIFFERENT (the conservative choice)."""
    try:
        p = path
        for _ in range(40):
            if p.exists():
                return ("dev", os.stat(str(p)).st_dev)
            if p.parent == p:
                break
            p = p.parent
        anchor = path.anchor or str(path)
        return ("anchor", anchor)
    except Exception:
        return ("unique", id(path))


def _free_bytes(path: Path) -> int | None:
    """Free bytes on the volume holding path (probing the nearest existing
    ancestor). None if it cannot be determined."""
    try:
        p = path
        for _ in range(40):
            if p.exists():
                return shutil.disk_usage(str(p)).free
            if p.parent == p:
                break
            p = p.parent
        probe = path.anchor or str(Path.home())
        return shutil.disk_usage(probe).free
    except Exception:
        return None


@dataclass
class JobEstimate:
    output_format: str            # "exfat" | "ffpfsc"
    src_type: str                 # "folder" | "exfat" | "ffpkg"
    build_dir: Path
    final_dir: Path
    source_size: int              # bytes (exact)
    final_size: int               # bytes (exact for exfat, estimated for ffpfsc)
    peak_build: int               # bytes peak on build_dir during the build
    final_exact: bool             # is final_size exact (True) or estimated (False)?
    # The exact minimum the build cannot possibly go below on build_dir. For
    # ffpfsc this is just the temp/source image (the compressed output only adds
    # to it); used to decide block-vs-warn.
    build_exact_min: int = 0
    note: str = ""


def estimate_job(job) -> JobEstimate:
    """Estimate space for one BuildJob. Read-only; never raises."""
    build_dir = job.build_dir()
    final_dir = job.final_dir()
    src = Path(job.src_path)
    out_fmt = getattr(job, "output_format", "ffpfsc")
    src_type = job.src_type

    # ---- source size (exact) -------------------------------------------------
    source_size = int(getattr(job, "size_bytes", 0) or 0)

    # ---- exFAT image size (exact) for folder sources -------------------------
    # For a dump folder we can size the exFAT image precisely. For image sources
    # (.exfat/.ffpkg) the source file itself is the image, so use its size.
    exfat_image_size = 0
    if src_type == "folder":
        if calculate_exfat_size is not None and src.is_dir():
            try:
                mb, _cluster, total_raw, _files = calculate_exfat_size(src, None)
                exfat_image_size = int(mb) * 1024 * 1024
                if not source_size:
                    source_size = int(total_raw)
            except Exception:
                # Fall back to source size + a conservative slack if the walk fails.
                exfat_image_size = int(source_size * 1.05) + 64 * 1024 * 1024
        else:
            exfat_image_size = int(source_size * 1.05) + 64 * 1024 * 1024
    else:
        # image source: the file's size (size_bytes was set from the file)
        exfat_image_size = source_size

    if out_fmt == "exfat":
        # dump -> exFAT: final IS the exFAT image (exact). No temp, no compress.
        final_size = exfat_image_size
        peak_build = exfat_image_size
        return JobEstimate(
            output_format="exfat", src_type=src_type, build_dir=build_dir,
            final_dir=final_dir, source_size=source_size, final_size=final_size,
            peak_build=peak_build, final_exact=True, build_exact_min=peak_build,
            note="exFAT image size is exact.",
        )

    # ---- ffpfsc output (folder, exfat, or ffpkg source) ----------------------
    # Final compressed size is unknowable -> assume no compression (conservative).
    if src_type == "folder":
        # Pass 1 builds a temp exFAT (exact), Pass 2 compresses it. Both coexist
        # before the temp is deleted, so peak = temp exFAT + estimated final.
        temp_image = exfat_image_size
    else:
        # pack_file compresses the source image directly; no temp exFAT.
        temp_image = source_size

    est_final = temp_image  # conservative: final ffpfsc ~= input image (no gain)
    peak_build = temp_image + est_final
    return JobEstimate(
        output_format="ffpfsc", src_type=src_type, build_dir=build_dir,
        final_dir=final_dir, source_size=source_size, final_size=est_final,
        peak_build=peak_build, final_exact=False, build_exact_min=temp_image,
        note="Final .ffpfsc size estimated assuming no compression.",
    )


@dataclass
class VolumeCheck:
    volume: object
    label: str                    # human path(s) on this volume
    required: int                 # required incl. safety margin
    required_exact_min: int       # exact minimum (no estimate) for block decision
    free: int | None
    status: str                   # pass / warn / block


@dataclass
class PreflightResult:
    volumes: list[VolumeCheck] = field(default_factory=list)
    status: str = PASS            # worst status across volumes
    estimates: list[JobEstimate] = field(default_factory=list)

    @property
    def can_start(self) -> bool:
        return self.status != BLOCK


def check_queue(jobs, margin: bool = True) -> PreflightResult:
    """Aggregate per-volume space requirements for a queue of BuildJobs.

    Builds are sequential, so on the build (staging) volume we need the LARGEST
    single peak, while on the final (archive) volume we need the SUM of all final
    outputs (every completed file accumulates there). When build and final live
    on the same volume, their requirements are combined.
    """
    estimates = [estimate_job(j) for j in jobs]

    # Accumulate requirements per volume id.
    # build volume: track max peak (sequential) + exact min for block test.
    # final volume: track sum of final outputs + exact-sum for block test.
    vol_meta: dict = {}   # vid -> {"paths": set, "build_peak": int, "build_exact": int,
                          #         "final_sum": int, "final_exact_sum": int}

    def _slot(vid, path):
        m = vol_meta.setdefault(vid, {"paths": set(), "build_peak": 0, "build_exact": 0,
                                      "final_sum": 0, "final_exact_sum": 0})
        m["paths"].add(str(path))
        return m

    for e in estimates:
        bvid = _volume_id(e.build_dir)
        fvid = _volume_id(e.final_dir)
        bm = _slot(bvid, e.build_dir)
        # sequential builds: peak build space is the max single peak on this volume
        bm["build_peak"] = max(bm["build_peak"], e.peak_build)
        bm["build_exact"] = max(bm["build_exact"], e.build_exact_min)

        if fvid == bvid:
            # same volume: the final output also accumulates here; add to sums.
            bm["final_sum"] += e.final_size
            bm["final_exact_sum"] += (e.final_size if e.final_exact else 0)
        else:
            fm = _slot(fvid, e.final_dir)
            fm["final_sum"] += e.final_size
            fm["final_exact_sum"] += (e.final_size if e.final_exact else 0)

    volumes: list[VolumeCheck] = []
    worst = PASS
    for vid, m in vol_meta.items():
        # Required (conservative): peak build (one at a time) + accumulated finals.
        # When build and final share the volume the move is a rename (final isn't a
        # second copy beyond peak), so required = max(build_peak, build space already
        # counted) ... we use build_peak + final_sum which is the safe upper bound:
        # during the largest build the temp+output coexist (build_peak) AND earlier
        # finished outputs already sit on disk (final_sum minus this build's final).
        # Using build_peak + final_sum slightly over-reserves -> conservative.
        raw_required = m["build_peak"] + m["final_sum"]
        required = _with_margin(raw_required) if margin else raw_required
        # Exact minimum that cannot be avoided (for block decision): exact build
        # min + exact finals only (estimates excluded).
        exact_min = m["build_exact"] + m["final_exact_sum"]

        first_path = sorted(m["paths"])[0] if m["paths"] else ""
        label = first_path + (f" (+{len(m['paths']) - 1} more)" if len(m["paths"]) > 1 else "")
        free = _free_bytes(Path(first_path)) if first_path else None

        if free is None:
            status = WARN   # can't determine free space -> caution, don't green-light
        elif exact_min > free:
            status = BLOCK  # even the exact, unavoidable minimum doesn't fit
        elif required > free:
            status = WARN   # conservative estimate doesn't fit; real build might
        else:
            status = PASS

        volumes.append(VolumeCheck(volume=vid, label=label, required=required,
                                   required_exact_min=exact_min, free=free, status=status))
        # worst-status escalation
        if status == BLOCK or worst == BLOCK:
            worst = BLOCK
        elif status == WARN:
            worst = WARN

    return PreflightResult(volumes=volumes, status=worst, estimates=estimates)
