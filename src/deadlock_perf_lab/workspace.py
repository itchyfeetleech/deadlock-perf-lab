"""Workspace configuration and immutable, randomized experiment plans."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import math
import fnmatch
import random
import shlex
import uuid

from . import __version__
from .profiles import catalog, frozen
from .storage import LabError, digest, fingerprint, read_json, write_json
from .system import discover_install, game_identity, identity


def load_workspace(workspace: Path) -> dict:
    config = read_json(workspace / "lab.json")
    if config.get("schema") != 1:
        raise LabError("Unsupported workspace schema. This release reads schema 1.")
    scenario = config.get("scenario", {})
    if scenario.get("mode") not in {"replay", "bots"}:
        raise LabError("scenario.mode must be replay or bots")
    for key, minimum, maximum in (("sample_s", 1, 600), ("warmup_s", 0, 600), ("settle_s", 0, 300),
                                   ("cooldown_s", 0, 300), ("budget_fps", 1, 2000)):
        value = scenario.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise LabError(f"scenario.{key} must be between {minimum} and {maximum}.")
    tick = scenario.get("tick")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise LabError("scenario.tick must be a nonnegative integer.")
    return config


def initialize(workspace: Path, install: str | None = None, replay: str | None = None) -> dict:
    if (workspace / "lab.json").exists():
        raise LabError(f"Workspace already exists: {workspace}. Edit lab.json to change it.")
    found = Path(install).expanduser().resolve() if install else discover_install()
    config = {"schema": 1, "install": str(found) if found else None,
              "scenario": {"mode": "replay", "replay": replay or "", "tick": 70000, "player": "",
                           "map": "dl_midtown", "sample_s": 30, "warmup_s": 45, "settle_s": 5,
                           "cooldown_s": 5, "budget_fps": 144},
              "conditions": {"resolution": "record me", "graphics_preset": "record me",
                             "proton_version": "record me", "display_mode": "record me",
                             "notes": "Record upscaling, frame generation, VSync/VRR, driver overrides and background apps."}}
    write_json(workspace / "lab.json", config)
    for folder in ("profiles", "sessions", "imports"):
        (workspace / folder).mkdir(exist_ok=True)
    # Outside benchmark runs this neutral config leaves logging off.
    from .storage import atomic_write
    atomic_write(workspace / "capture.conf", b"no_display\nautostart_log=0\n")
    return config


def launch_options(workspace: Path) -> str:
    return f"env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE={shlex.quote(str(workspace / 'capture.conf'))} %command%"


def make_plan(workspace: Path, cases: list[str], rounds: int, seed: int, *, demo: bool = False,
              experimental: bool = False, manual: bool = False, preset: str = "custom") -> tuple[Path, dict]:
    config = load_workspace(workspace)
    if preset not in {"custom", "scout", "screen", "confirm"}:
        raise LabError("Preset must be scout, screen, confirm or custom.")
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
    scenario["load_guard_s"] = 1
    scenario["ready_protocol"] = "source2-demo-signon-v2"
    scenario["camera_guard_s"] = .1
    if preset == "scout":
        scenario.update(sample_s=5, warmup_s=2, settle_s=1, cooldown_s=0)
    elif preset == "screen":
        scenario.update(sample_s=10, warmup_s=5, settle_s=1, cooldown_s=0)
    elif preset == "confirm":
        scenario.update(sample_s=30, warmup_s=45, settle_s=5, cooldown_s=5)
    install = Path(config["install"]) if config["install"] else None
    if not demo and not manual:
        if not install or not (install / "game/citadel/gameinfo.gi").is_file():
            raise LabError("Deadlock install missing; set install in lab.json or use --demo.")
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


def session_path(workspace: Path, value: str) -> Path:
    if value == "latest":
        paths = sorted(p for p in (workspace / "sessions").iterdir() if (p / "plan.json").is_file())
        if not paths:
            raise LabError("No sessions yet. Run dpl demo or dpl plan.")
        return paths[-1]
    path = Path(value).expanduser()
    if path.is_dir() and (path / "plan.json").is_file():
        return path.resolve()
    from .profiles import valid_id
    # Session IDs contain uppercase UTC T/Z; accept the generated pattern too.
    if not __import__("re").fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        valid_id(value)
    path = workspace / "sessions" / value
    if not (path / "plan.json").is_file():
        raise LabError(f"Session not found: {value}")
    return path
