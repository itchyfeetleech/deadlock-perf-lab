"""Throughput inspection and provisional screening candidates."""
from datetime import datetime
from pathlib import Path
import statistics

from .analysis import analyze
from .storage import read_json


def timings(session: Path) -> dict:
    plan = read_json(session / "plan.json")
    durations = []
    phases = {}
    for path in sorted((session / "runs").glob("*/result.json")):
        result = read_json(path)
        if result.get("status") != "ok" or not result.get("finished_at"):
            continue
        for name, value in result.get("phase_timings_s", {}).items():
            phases.setdefault(name, []).append(value)
        durations.append((datetime.fromisoformat(result["finished_at"]) -
                          datetime.fromisoformat(result["started_at"])).total_seconds())
    median = statistics.median(durations) if durations else None
    remaining = len(plan["schedule"]) - len(durations)
    return {"session": plan["id"], "completed": len(durations), "planned": len(plan["schedule"]),
            "rounds": plan["rounds"], "treatments": len(plan["profiles"]) - 1,
            "sample_s": plan["context"]["scenario"]["sample_s"],
            "median_phases_s": {k: statistics.median(v) for k, v in phases.items()}, "median_run_s": median,
            "mean_run_s": statistics.fmean(durations) if durations else None,
            "estimated_remaining_minutes": median * remaining / 60 if median is not None else None}


def shortlist(session: Path, top: int = 5) -> list[dict]:
    report = analyze(session)
    candidates = [c for c in report["comparisons"] if c["delta_pct"] is not None]
    return sorted(candidates, key=lambda c: c["delta_pct"], reverse=True)[:top]
