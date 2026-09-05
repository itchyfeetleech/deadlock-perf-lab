"""Explicit frame-time definitions; no outlier clipping or invented values."""
from __future__ import annotations

import math
import statistics

from .storage import LabError

METRIC_VERSION = "frametime-v1"


def percentile(values: list[float], p: float) -> float:
    """Linear interpolation at (n - 1) * p; p in [0, 1]."""
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def summarize(frames: list[float], *, per_frame: bool = True, budget_ms: float = 6.944444) -> dict:
    if len(frames) < 10:
        raise LabError("Capture needs at least 10 valid frame times.")
    if any(not math.isfinite(x) or x <= 0 for x in frames):
        raise LabError("Frame times must be finite and positive.")
    if not math.isfinite(budget_ms) or budget_ms <= 0:
        raise LabError("Frame budget must be finite and positive.")
    ordered = sorted(frames, reverse=True)
    mean = statistics.fmean(frames)
    # Slowest-fraction mean and percentile inverse are deliberately separate.
    low1 = 1000 / statistics.fmean(ordered[:max(1, math.ceil(len(frames) * .01))])
    low01 = 1000 / statistics.fmean(ordered[:max(1, math.ceil(len(frames) * .001))])
    return {
        "metric_version": METRIC_VERSION,
        "samples": len(frames),
        "per_frame": per_frame,
        "avg_fps": 1000 / mean,
        "low_1_fps": low1 if per_frame else None,
        "low_01_fps": low01 if per_frame and len(frames) >= 1000 else None,
        "p99_inverse_fps": 1000 / percentile(frames, .99),
        "mean_frame_ms": mean,
        "median_frame_ms": statistics.median(frames),
        "p95_frame_ms": percentile(frames, .95),
        "p99_frame_ms": percentile(frames, .99),
        "max_frame_ms": max(frames),
        "stdev_frame_ms": statistics.pstdev(frames),
        "over_budget_pct": sum(x > budget_ms for x in frames) / len(frames) * 100,
        "budget_ms": budget_ms,
        "stalls_over_50ms": sum(x > 50 for x in frames),
        "stalls_over_100ms": sum(x > 100 for x in frames),
        "frame_time_sum_s": sum(frames) / 1000 if per_frame else None,
    }
