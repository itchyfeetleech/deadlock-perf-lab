"""Workspace configuration, capture setup and session lookup."""
from __future__ import annotations

from pathlib import Path
import math
import shlex

from .storage import LabError, atomic_write, read_json, write_json
from .system import discover_install


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
    atomic_write(workspace / "capture.conf", b"no_display\nautostart_log=0\n")
    return config


def launch_options(workspace: Path) -> str:
    return f"env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE={shlex.quote(str(workspace / 'capture.conf'))} %command%"


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
