"""Portable, offline reports. Export allowlists exclude logs and backups."""
from __future__ import annotations

import csv
import html
import io
import json
import math
from pathlib import Path
from importlib.resources import files
import statistics
import zipfile

from .analysis import analyze
from .storage import atomic_write, fingerprint, write_json


def chart_series(times: list[float], frames: list[float], points: int = 360) -> list[list[float]]:
    """Each time bin retains min/mean/max so isolated stalls remain visible."""
    step = max(1, math.ceil(len(frames) / points))
    return [[round(times[i] - times[0], 4), round(min(frames[i:i + step]), 4),
             round(statistics.fmean(frames[i:i + step]), 4), round(max(frames[i:i + step]), 4)]
            for i in range(0, len(frames), step)]


def public_payload(analysis: dict) -> dict:
    result = json.loads(json.dumps(analysis))
    scenario = result["context"]["scenario"]
    if scenario.get("replay"):
        # The content hash identifies the replay without exposing a username,
        # filesystem path or match ID. Player selection is anonymized too.
        scenario["replay"] = "local replay (identified by SHA-256)"
    scenario.pop("replay_command", None)
    if scenario.get("player"):
        scenario["player"] = "target-" + fingerprint(str(scenario["player"]))[:10]
    for record in result["runs"]:
        record.pop("capture_metadata", None)
    # This report contains user-authored labels/notes; arbitrary secrets typed
    # into those cannot be inferred or reliably removed. Document that boundary.
    return result


def fmt(value: float | None, suffix: str = "", signed: bool = False) -> str:
    if value is None:
        return "—"
    return (f"{value:+.1f}" if signed else f"{value:.1f}") + suffix


def markdown_report(result: dict) -> str:
    base = result["baseline"]
    lines = ["# Deadlock Perf Lab", "", f"Session: `{result['session']}`", "",
             "**DEMO DATA — not game measurements.**" if result["synthetic"] else "Measured capture report.", "",
             f"Baseline: {fmt(base['avg_fps'], ' FPS')} · CV {fmt(base['cv_pct'], '%')} · drift {fmt(base['drift_pct'], '%', True)}.", "",
             "| Treatment | Rounds | Average FPS | Change | 95% interval | Verdict |",
             "|---|---:|---:|---:|---|---|"]
    for c in result["comparisons"]:
        ci = " to ".join(fmt(x, "%", True) for x in c["ci95_pct"]) if c["ci95_pct"] else "insufficient repeats"
        label = c["name"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {label} | {len(c['paired_rounds'])} | {fmt(c['avg_fps'])} | {fmt(c['delta_pct'], '%', True)} | {ci} | {c['verdict']} |")
    lines += ["", "## Measurement notes", ""]
    lines += [f"- {w}" for w in result["warnings"]]
    for c in result["comparisons"]:
        lines += [f"- {c['case']}: {reason}" for reason in c["reasons"]]
    lines += ["", "95% intervals bootstrap complete rounds, not individual frames. They are exploratory and not corrected for testing many treatments.",
              "Average FPS = 1000 / mean frame time. 1% low = 1000 / mean of the slowest ceil(1% × frames) frame times.",
              "FPS does not measure input latency, network delay, visual quality or live-match competitiveness.", ""]
    return "\n".join(lines)


def generate_report(session: Path, threshold: float = 3) -> Path:
    result = public_payload(analyze(session, threshold))
    output = session / "report"
    output.mkdir(exist_ok=True)
    write_json(output / "summary.json", result)
    atomic_write(output / "summary.md", markdown_report(result).encode())
    stream = io.StringIO(newline="")
    keys = ["id", "case", "round", "synthetic", "avg_fps", "low_1_fps", "low_01_fps", "p99_frame_ms", "max_frame_ms",
            "over_budget_pct", "stalls_over_50ms", "samples", "capture_sha256"]
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    for record in result["runs"]:
        values = {key: record.get(key, record["metrics"].get(key, "")) for key in keys}
        # Prevent CSV formula execution in spreadsheet programs.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in values.items()})
    atomic_write(output / "runs.csv", stream.getvalue().encode())
    escape = html.escape
    comparison_rows = []
    for c in result["comparisons"]:
        comparison_rows.append(f'<tr><td><strong>{escape(c["name"])}</strong><small>{escape(c["case"])}</small></td>'
                               f'<td>{fmt(c["avg_fps"])}</td><td>{fmt(c["metrics"]["low_1_fps"])}</td>'
                               f'<td>{fmt(c["metrics"]["p99_frame_ms"])}</td>'
                               f'<td>{fmt(c["delta_pct"], "%", True)}</td><td>{len(c["paired_rounds"])}</td>'
                               f'<td><span class="badge">{escape(c["verdict"])}</span></td></tr>')
    notes = list(result["warnings"])
    for c in result["comparisons"]:
        notes.extend(f"{c['name']}: {reason}" for reason in c["reasons"])
    for record in result["runs"]:
        for blocker in record.get("quality_blockers", []):
            if blocker not in notes:
                notes.append(blocker)
    page = files("deadlock_perf_lab").joinpath("assets/report.html").read_text()
    substitutions = {
        "__TITLE__": escape(result["session"]),
        "__FPS__": fmt(result["baseline"]["avg_fps"]),
        "__CV__": fmt(result["baseline"]["cv_pct"], "%"),
        "__DRIFT__": fmt(result["baseline"]["drift_pct"], "%", True),
        "__RUNS__": f'{result["valid_runs"]}<span> / {result["expected_runs"]}</span>',
        "__ROWS__": "".join(comparison_rows) or '<tr><td colspan="7">Baseline-only session. Add a treatment to compare changes.</td></tr>',
        "__NOTES__": "".join(f"<li>{escape(n)}</li>" for n in dict.fromkeys(notes)) or "<li>No quality warnings.</li>",
        "__DATA__": json.dumps(result, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026"),
    }
    for marker, value in substitutions.items():
        page = page.replace(marker, value)
    atomic_write(output / "index.html", page.encode())
    return output / "index.html"


def bundle(session: Path, destination: Path, threshold: float = 3) -> Path:
    report = generate_report(session, threshold).parent
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("index.html", "summary.json", "summary.md", "runs.csv"):
            archive.write(report / name, name)
    return destination
