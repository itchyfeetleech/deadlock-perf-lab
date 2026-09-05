"""Round-level comparisons. Individual frames are not independent trials."""
from __future__ import annotations

import random
import statistics
from pathlib import Path

from .metrics import percentile
from .storage import LabError, digest, read_json
from .workspace import verify_plan


def bootstrap_ci(values: list[float], *, seed: int = 47, samples: int = 4000) -> list[float] | None:
    if len(values) < 3:
        return None
    rng = random.Random(seed)
    boot = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(samples))
    return [percentile(boot, .025), percentile(boot, .975)]


def aggregate_metrics(records: list[dict]) -> dict:
    # Equal weight per capture; never silently pool frames across rounds.
    keys = ("avg_fps", "low_1_fps", "low_01_fps", "p99_frame_ms", "over_budget_pct")
    result = {}
    for key in keys:
        values = [r["metrics"].get(key) for r in records]
        result[key] = statistics.fmean(values) if values and all(v is not None for v in values) else None
    return result


def analyze(session: Path, threshold: float = 3) -> dict:
    import math
    if not math.isfinite(threshold) or threshold <= 0:
        raise LabError("Threshold must be finite and positive.")
    plan = read_json(session / "plan.json")
    verify_plan(plan)
    records = []
    for path in sorted((session / "runs").glob("*/result.json")):
        record = read_json(path)
        review_path = path.parent / "review.json"
        if review_path.exists():
            review = read_json(review_path)
            if review.get("result_sha256") == digest(path):
                record["operator_review"] = review
                record["quality_blockers"] = [b for b in record.get("quality_blockers", [])
                                              if b not in review.get("confirmed", [])]
        record["_directory"] = str(path.parent)
        records.append(record)
    warnings = []
    valid = []
    excluded = []
    seen = set()
    for record in records:
        why = []
        raw_name = record.get("raw_capture", "")
        raw = Path(record.pop("_directory")) / raw_name
        if record.get("status") == "ok":
            if not raw_name or Path(raw_name).is_absolute() or ".." in Path(raw_name).parts or not raw.is_file():
                why.append("raw capture missing or invalid")
            elif digest(raw) != record.get("capture_sha256"):
                why.append("raw capture changed after measurement")
            index = record.get("index", 0)
            planned = plan["schedule"][index - 1] if isinstance(index, int) and 0 < index <= len(plan["schedule"]) else {}
            if any(record.get(k) != planned.get(k) for k in ("index", "case", "round")):
                why.append("run does not match the planned schedule")
            profile = plan["profiles"].get(record.get("case"), {})
            if record.get("profile_sha256") != profile.get("sha256"):
                why.append("treatment fingerprint differs from the plan")
        if record.get("status") != "ok":
            why.append(record.get("error", "failed capture"))
        if record.get("context_key") != plan["context_key"]:
            why.append("incompatible benchmark conditions")
        if record.get("synthetic") != plan["synthetic"]:
            why.append("mixed synthetic and measured evidence")
        if record.get("capture_sha256") in seen:
            why.append("duplicate raw capture")
        if record.get("capture_sha256"):
            seen.add(record["capture_sha256"])
        if not why:
            valid.append(record)
        else:
            excluded.append({"id": record.get("id"), "reasons": why})
    if plan["synthetic"]:
        warnings.append("DEMO DATA — generated to demonstrate the workflow. These are not Deadlock performance findings.")
    if len(valid) < len(plan["schedule"]):
        warnings.append(f"Incomplete session: {len(valid)}/{len(plan['schedule'])} usable runs. Missing/failed runs can bias a comparison.")
    base = [r for r in valid if r["case"] == "baseline"]
    base_fps = [r["metrics"]["avg_fps"] for r in base]
    base_cv = statistics.pstdev(base_fps) / statistics.fmean(base_fps) * 100 if base_fps else None
    drift = (base_fps[-1] / base_fps[0] - 1) * 100 if len(base_fps) >= 2 else None
    if base_cv is not None and base_cv > threshold:
        warnings.append(f"Baseline variation is high (CV {base_cv:.1f}%). Recheck thermals, camera, scene and background load.")
    if drift is not None and abs(drift) > threshold:
        warnings.append(f"Opening-to-closing baseline drift is {drift:+.1f}%. Rerun under stable conditions.")
    scenario = plan["context"]["scenario"]
    if scenario.get("mode") == "bots":
        warnings.append("Bot matches have random behavior and camera transitions; treat these results as exploratory.")
    for record in valid:
        for warning in record.get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)
    comparisons = []
    for case, profile in plan["profiles"].items():
        if case == "baseline":
            continue
        own = [r for r in valid if r["case"] == case]
        deltas = []
        low_deltas = []
        paired_rounds = []
        for round_index in range(1, plan["rounds"] + 1):
            controls = [r for r in base if r["round"] == round_index]
            treatments = [r for r in own if r["round"] == round_index]
            if len(controls) != 2 or len(treatments) != 1:
                continue
            control = statistics.fmean(r["metrics"]["avg_fps"] for r in controls)
            deltas.append((treatments[0]["metrics"]["avg_fps"] / control - 1) * 100)
            paired_rounds.append(round_index)
            lows = [r["metrics"].get("low_1_fps") for r in controls]
            low = treatments[0]["metrics"].get("low_1_fps")
            if all(x is not None for x in lows) and low is not None:
                low_deltas.append((low / statistics.fmean(lows) - 1) * 100)
        ci = bootstrap_ci(deltas)
        delta = statistics.fmean(deltas) if deltas else None
        reasons = []
        if len(deltas) < 5:
            reasons.append("At least 5 complete paired rounds are required for a directional verdict.")
        if len(deltas) != plan["rounds"]:
            reasons.append("Some planned rounds are incomplete.")
        if base_cv is None or base_cv > threshold or drift is None or abs(drift) > threshold:
            reasons.append("Baseline stability checks did not pass.")
        if scenario.get("mode") == "bots":
            reasons.append("Bot scenario is exploratory.")
        if any(r.get("quality_blockers") for r in own + base):
            reasons.append("Capture or scenario verification needs review.")
        verdict = "inconclusive"
        if not reasons and ci:
            if ci[0] > threshold:
                verdict = "improved"
            elif ci[1] < -threshold:
                verdict = "regressed"
            elif ci[0] >= -threshold and ci[1] <= threshold:
                verdict = "within threshold"
            else:
                reasons.append("The confidence interval overlaps the practical threshold.")
        comparisons.append({"case": case, "name": profile.get("name", case), "kind": profile["kind"],
                            "metrics": aggregate_metrics(own),
                            "runs": len(own), "paired_rounds": paired_rounds, "delta_pct": delta,
                            "ci95_pct": ci, "round_deltas_pct": deltas,
                            "low_1_delta_pct": statistics.fmean(low_deltas) if low_deltas else None,
                            "avg_fps": statistics.fmean(r["metrics"]["avg_fps"] for r in own) if own else None,
                            "verdict": "demo" if plan["synthetic"] else verdict,
                            "reasons": reasons})
    return {"schema": 1, "session": plan["id"], "synthetic": plan["synthetic"], "threshold_pct": threshold,
            "baseline": {"metrics": aggregate_metrics(base), "runs": len(base), "avg_fps": statistics.fmean(base_fps) if base_fps else None,
                         "cv_pct": base_cv, "drift_pct": drift},
            "comparisons": comparisons, "warnings": warnings, "excluded": excluded,
            "valid_runs": len(valid), "expected_runs": len(plan["schedule"]),
            "context": plan["context"], "runs": valid}
