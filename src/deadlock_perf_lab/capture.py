"""MangoHud log reader with explicit time windows and sampling fidelity."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import math
from pathlib import Path
import statistics

from .metrics import summarize
from .storage import LabError, digest


def chart_series(times: list[float], frames: list[float], points: int = 360) -> list[list[float]]:
    """Each time bin retains min/mean/max so isolated stalls remain visible."""
    step = max(1, math.ceil(len(frames) / points))
    return [[round(times[i] - times[0], 4), round(min(frames[i:i + step]), 4),
             round(statistics.fmean(frames[i:i + step]), 4), round(max(frames[i:i + step]), 4)]
            for i in range(0, len(frames), step)]


@dataclass
class Capture:
    frames: list[float]
    times: list[float]
    telemetry: dict[str, list[float]]
    metadata: dict
    warnings: list[str] = field(default_factory=list)

    def metrics(self, budget_ms: float = 1000 / 144) -> dict:
        result = summarize(self.frames, per_frame=self.metadata["per_frame"], budget_ms=budget_ms)
        result["duration_s"] = self.times[-1] - self.times[0] if len(self.times) > 1 else 0
        result["telemetry"] = {
            k: {"mean": statistics.fmean(v), "max": max(v)}
            for k, v in self.telemetry.items() if v
        }
        return result


def read_mangohud(path: Path, *, start_s: float = 0, duration_s: float | None = None,
                  interval_ms: float | None = None) -> Capture:
    """MangoHud elapsed is nanoseconds since logger start, not wall time.

    By default imports are conservatively classified as interval samples.
    A per-frame assertion (interval_ms=0) is also checked against elapsed
    coverage; positive frame-time stalls are never silently discarded.
    """
    if start_s < 0 or not math.isfinite(start_s):
        raise LabError("start_s must be finite and nonnegative")
    if duration_s is not None and (not math.isfinite(duration_s) or duration_s <= 0):
        raise LabError("duration_s must be finite and positive")
    if interval_ms is not None and (not math.isfinite(interval_ms) or interval_ms < 0):
        raise LabError("interval_ms must be finite and nonnegative")
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.reader(f))
    except OSError as exc:
        raise LabError(f"Cannot read capture {path}: {exc}") from exc
    header_index = next((i for i, row in enumerate(rows)
                         if "frametime" in [x.strip().lower() for x in row]
                         and "fps" in [x.strip().lower() for x in row]), None)
    if header_index is None:
        raise LabError("Not a MangoHud data CSV: expected fps and frametime columns (not a summary CSV).")
    header = [x.strip().lower() for x in rows[header_index]]
    if len(header) != len(set(header)):
        raise LabError("Capture has duplicate column names.")
    system = {}
    for i, row in enumerate(rows[:header_index]):
        if row and row[0].strip().lower() == "os" and i + 1 < header_index:
            system = dict(zip([x.strip() for x in row], rows[i + 1]))
    parsed = []
    bad = 0
    last_time = -1.0
    cumulative = 0.0
    for row in rows[header_index + 1:]:
        if not row or not any(x.strip() for x in row):
            continue
        item = dict(zip(header, row))
        try:
            frame = float(item["frametime"])
            if frame <= 0 or not math.isfinite(frame):
                raise ValueError("invalid frame")
            cumulative += frame / 1000
            elapsed = float(item["elapsed"]) / 1e9 if "elapsed" in header else cumulative
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("invalid elapsed")
        except (ValueError, KeyError):
            bad += 1
            continue
        if elapsed < last_time:
            raise LabError("Capture elapsed timestamps go backwards; concatenated/reset logs cannot be compared.")
        last_time = elapsed
        parsed.append((elapsed, frame, item))
    if "elapsed" not in header and interval_ms != 0:
        raise LabError("CSV has no elapsed column. Specify --interval-ms 0 only for confirmed per-frame logs.")
    stop = start_s + duration_s if duration_s is not None else math.inf
    selected = [(t, ft, row) for t, ft, row in parsed if start_s <= t < stop]
    if len(selected) < 10:
        raise LabError(f"Only {len(selected)} samples in the selected window; need at least 10.")
    warnings = []
    if bad:
        warnings.append(f"Excluded {bad} malformed/nonpositive/nonfinite rows in the source log.")
    if interval_ms is None:
        warnings.append("Logging interval unknown; true 1% and 0.1% lows are unavailable. Declare the capture interval.")
    per_frame = interval_ms == 0
    times = [x[0] for x in selected]
    frames = [x[1] for x in selected]
    if per_frame and "elapsed" in header:
        # Elapsed coverage should track the sum of frame times (first frame
        # straddles the boundary). Reject mistaken log_interval=100 imports.
        coverage = sum(frames[1:]) / 1000 / max(times[-1] - times[0], 1e-9)
        if not .8 <= coverage <= 1.2:
            raise LabError(f"Declared per-frame capture covers {coverage:.1%} of elapsed time. "
                           "Use the real --interval-ms; per-frame capture requires MangoHud log_interval=0.")
    if not per_frame:
        warnings.append("Interval samples: FPS is a sampled estimate; tail samples are not true per-frame lows.")
    if duration_s is not None:
        median_gap = statistics.median([b - a for a, b in zip(times, times[1:])])
        tolerance = max(.25, median_gap * 3)
        if times[0] > start_s + tolerance or times[-1] < stop - tolerance:
            raise LabError("Capture does not cover the requested measurement window; no partial result was accepted.")
    telemetry = {}
    for key in ("cpu_load", "gpu_load", "cpu_temp", "gpu_temp", "gpu_core_clock", "gpu_mem_clock",
                "gpu_vram_used", "gpu_power", "cpu_power", "ram_used"):
        values = []
        for _, _, row in selected:
            try:
                value = float(row[key])
                if math.isfinite(value) and value >= 0:
                    values.append(value)
            except (KeyError, ValueError):
                pass
        telemetry[key] = values
    return Capture(frames, times, telemetry, {
        "format": "mangohud", "sha256": digest(path), "system": system,
        "interval_ms": interval_ms, "per_frame": per_frame, "invalid_rows": bad,
        "start_s": start_s, "requested_duration_s": duration_s,
    }, warnings)
