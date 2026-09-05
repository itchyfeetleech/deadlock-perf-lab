"""Declarative benchmark treatments, copied and hashed into every plan."""
from __future__ import annotations

from importlib.resources import files
import json
from pathlib import Path
import re

from .storage import LabError, fingerprint, read_json, write_json

ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
# Commands that change the controlled scenario, run arbitrary cfgs, or mutate
# user input bindings do not belong in a performance treatment.
BLOCKED = {"exec", "execifexists", "alias", "bind", "bindtoggle", "unbind", "unbindall", "connect",
           "disconnect", "quit", "exit", "map", "changelevel", "playdemo", "record", "stop",
           "host_writeconfig", "host_timescale", "sv_cheats", "plugin_load", "rcon", "script"}


def valid_id(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise LabError("IDs must be 1–64 lowercase letters, digits, hyphens or underscores; start with a letter/digit.")
    return value


def validate_autoexec(content: str) -> None:
    for number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        line = line.split("//", 1)[0].strip()
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s+(?:"([^";\r\n]*)"|([^";\r\n]+))', line)
        if not match or match[1].lower() in BLOCKED or match[1].lower().startswith(("demo_", "spec_", "citadel_solo_")):
            raise LabError(f"Config line {number} must be a cvar assignment, without command chaining or scenario commands.")


def validate_gameinfo(content: str) -> None:
    # A structural sanity check, not a full Source 2 KeyValues interpreter.
    text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*', lambda m: '""' if m[0].startswith('"') else '', content)
    depth = 0
    for c in text:
        depth += (c == "{") - (c == "}")
        if depth < 0:
            raise LabError("Unbalanced GameInfo braces.")
    if depth or "gameinfo" not in content.lower():
        raise LabError("Expected a complete GameInfo file with balanced braces.")


def validate(profile: dict) -> dict:
    valid_id(profile.get("id", ""))
    if profile.get("kind") not in {"none", "autoexec", "gameinfo", "launch", "manual"}:
        raise LabError("Profile kind must be none, autoexec, gameinfo, launch or manual.")
    if profile["id"] == "baseline" and profile["kind"] != "none":
        raise LabError("baseline is reserved for the unchanged installation.")
    if profile["kind"] in {"autoexec", "gameinfo"}:
        content = profile.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise LabError("Profile content is empty.")
        (validate_autoexec if profile["kind"] == "autoexec" else validate_gameinfo)(content)
    if profile["kind"] == "launch":
        flags = profile.get("flags", [])
        if not flags or any(x not in {"-vulkan", "-dx11", "-novid"} for x in flags):
            raise LabError("Automated launch profiles support -vulkan, -dx11 and -novid; use manual captures for other launch setups.")
        if "-vulkan" in flags and "-dx11" in flags:
            raise LabError("Choose one renderer per profile.")
    return profile


def catalog(workspace: Path | None = None) -> dict[str, dict]:
    profiles = json.loads(files("deadlock_perf_lab").joinpath("assets/profiles.json").read_text())
    result = {}
    for profile in profiles:
        if "asset" in profile:
            profile["content"] = files("deadlock_perf_lab").joinpath("assets/gameinfo", profile["asset"]).read_text()
        result[profile["id"]] = validate(profile)
    if workspace:
        for path in sorted((workspace / "profiles").glob("*.json")):
            profile = validate(read_json(path))
            if profile["id"] in result:
                raise LabError(f"Custom profile shadows a built-in: {profile['id']}")
            result[profile["id"]] = profile
    return result


def add_profile(workspace: Path, profile: dict) -> Path:
    validate(profile)
    if profile["id"] in catalog(workspace):
        raise LabError("Profile already exists. Use a new ID to preserve experiment history.")
    path = workspace / "profiles" / f"{profile['id']}.json"
    write_json(path, profile)
    return path


def frozen(profile: dict) -> dict:
    return {**profile, "sha256": fingerprint(profile)}
