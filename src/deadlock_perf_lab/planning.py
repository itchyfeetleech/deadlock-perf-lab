"""Frozen profiles, benchmark presets and randomized experiment schedules."""
from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
from pathlib import Path
import random
import uuid

from . import __version__
from .profiles import catalog, frozen
from .storage import LabError, digest, fingerprint, write_json
from .system import game_identity, identity
from .workspace import load_workspace


PRESETS = {
    "custom": {},
    "scout": {"sample_s": 5, "warmup_s": 2, "settle_s": 1, "cooldown_s": 0},
    "screen": {"sample_s": 10, "warmup_s": 5, "settle_s": 1, "cooldown_s": 0},
    "confirm": {"sample_s": 30, "warmup_s": 45, "settle_s": 5, "cooldown_s": 5},
}


def make_plan(workspace: Path, cases: list[str], rounds: int | None, seed: int, *, demo: bool = False,
              experimental: bool = False, manual: bool = False, preset: str = "custom") -> tuple[Path, dict]:
    config = load_workspace(workspace)
    if preset not in PRESETS:
        raise LabError("Preset must be scout, screen, confirm or custom.")
    if rounds is None:
        rounds = 1 if preset in {"scout", "screen"} else 5
    if not 1 <= rounds <= 30:
        raise LabError("rounds must be between 1 and 30; use at least 5 for a comparison.")
    available = catalog(workspace)
    expanded = []
    for expression in cases:
        expression = expression.strip()
        matched = sorted(c for c in available if fnmatch.fnmatchcase(c, expression))
        if not matched:
            raise LabError(f"No profiles match {expression!r}. See dpl profiles.")
        expanded.extend(matched)
    cases = list(dict.fromkeys(c for c in expanded if c != "baseline"))
    for case in cases:
        if case not in available:
            raise LabError(f"Unknown profile: {case}. See dpl profiles.")
        if available[case]["kind"] == "manual" and not manual:
            raise LabError(f"{case} is a manual treatment. Capture it separately and use dpl import.")
        if available[case]["kind"] == "gameinfo" and not experimental:
            raise LabError("Whole GameInfo swaps require --experimental. Review dpl profile show ID first.")
    scenario = dict(config["scenario"])
    scenario["load_guard_s"] = 0
    scenario["ready_protocol"] = "source2-demo-signon-v3"
    scenario["replay_launch"] = "startup"
    scenario["camera_guard_s"] = .1
    scenario.update(PRESETS[preset])
    install = Path(config["install"]) if config["install"] else None
    if not demo and not manual:
        if not install or not (install / "game/citadel/gameinfo.gi").is_file():
            raise LabError("Deadlock install missing; set install in lab.json, or try dpl demo without the game.")
        if scenario["mode"] == "replay":
            if not scenario["replay"]:
                raise LabError("Set scenario.replay in lab.json to a downloaded .dem before planning a live run.")
            replay = Path(scenario["replay"]).expanduser()
            if not replay.is_absolute():
                replay = install / "game/citadel" / replay
            if not replay.is_file():
                raise LabError(f"Replay not found: {replay}")
            try:
                scenario["replay_command"] = replay.resolve().relative_to((install / "game/citadel").resolve()).as_posix()
            except ValueError as exc:
                raise LabError("Place the replay under the game's game/citadel directory so Proton can address it consistently.") from exc
            scenario["replay"] = str(replay.resolve())
            scenario["replay_sha256"] = digest(replay)
    if manual:
        scenario["mode"] = "manual"
    machine = identity() if not demo else {"os": "Linux", "cpu": "Illustrative CPU", "gpu": ["Illustrative GPU"]}
    game = game_identity(install) if install and not demo else {"build_id": "demo", "baseline_files": {}}
    if not demo and not manual:
        current_base = game["baseline_files"]["game/citadel/gameinfo.gi"]
        for case in cases:
            if available[case].get("base_sha256") and available[case]["base_sha256"] != current_base:
                raise LabError(f"{case}: sweep base differs from your current GameInfo. Generate the sweep from the intended live baseline.")
    plan_profiles = {key: frozen(available[key]) for key in ["baseline", *cases]}
    rng = random.Random(seed)
    schedule = []
    for round_index in range(1, rounds + 1):
        order = cases.copy()
        rng.shuffle(order)
        # Each block has independent opening and closing controls.
        for case in ["baseline", *order, "baseline"] if cases else ["baseline"]:
            schedule.append({"index": len(schedule) + 1, "round": round_index, "case": case})
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    conditions = config["conditions"] if not demo else {
        "resolution": "1920×1080 (illustrative)", "graphics_preset": "Synthetic demonstration",
        "proton_version": "Not used", "display_mode": "Not used",
        "notes": "Generated data exercises the pipeline; no game or hardware measurements were taken."}
    context = {"scenario": scenario, "system": machine, "game": game, "conditions": conditions,
               "metric_version": "frametime-v1", "capture": "mangohud-per-frame", "synthetic": demo}
    plan = {"schema": 1, "version": __version__, "id": session_id, "synthetic": demo,
            "install": str(install) if install else None, "manual": manual, "seed": seed, "rounds": rounds,
            "profiles": plan_profiles, "schedule": schedule, "context": context,
            "preset": preset, "context_key": fingerprint(context), "created_at": datetime.now(timezone.utc).isoformat()}
    plan["plan_sha256"] = fingerprint(plan)
    session = workspace / "sessions" / session_id
    write_json(session / "plan.json", plan)
    write_json(session / "status.json", {"state": "planned", "completed": 0, "total": len(schedule)})
    return session, plan


def verify_plan(plan: dict) -> None:
    if plan.get("schema") != 1:
        raise LabError("Unsupported plan schema.")
    body = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if fingerprint(body) != plan.get("plan_sha256"):
        raise LabError("Plan changed after creation. Create a new plan to record those changes.")
