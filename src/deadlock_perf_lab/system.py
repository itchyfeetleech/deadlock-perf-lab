"""Read-only Linux discovery. Never changes governors, drivers or Steam."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import re
import shutil

from .storage import digest, read_json

APP_ID = "1422450"


def install_lock(install: Path) -> Path:
    key = hashlib.sha256(str(install.resolve()).encode()).hexdigest()[:24]
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "deadlock-perf-lab/locks" / f"{key}.lock"


def discover_install() -> Path | None:
    override = os.environ.get("DEADLOCK_INSTALL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    roots = [Path.home() / p for p in (
        ".local/share/Steam", ".steam/steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam")]
    libraries = list(roots)
    for root in roots:
        config = root / "steamapps/libraryfolders.vdf"
        if config.is_file():
            libraries.extend(Path(p.replace("\\\\", "\\")) for p in
                             re.findall(r'"path"\s+"([^"]+)"', config.read_text(errors="replace")))
    for library in libraries:
        for name in ("Deadlock", "deadlock"):
            candidate = library / "steamapps/common" / name
            if (candidate / "game/citadel/gameinfo.gi").is_file():
                return candidate.resolve()
    return None


def identity() -> dict:
    cpu = "unknown"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        match = re.search(r"model name\s*:\s*(.+)", cpuinfo.read_text(errors="replace"))
        if match:
            cpu = match[1].strip()
    gpu = []
    for device in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        try:
            gpu.append({"vendor": (device / "vendor").read_text().strip(),
                        "device": (device / "device").read_text().strip(),
                        "driver": (device / "driver").resolve().name})
        except OSError:
            pass
    memory = "unknown"
    if Path("/proc/meminfo").is_file():
        memory = Path("/proc/meminfo").read_text().splitlines()[0].split(":", 1)[1].strip()
    governors = sorted({p.read_text().strip() for p in
                        Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor")})
    return {"os": platform.system(), "kernel": platform.release(), "architecture": platform.machine(),
            "cpu": cpu, "logical_cpus": os.cpu_count(), "gpu": gpu, "memory": memory,
            "governors": governors}


def game_identity(install: Path) -> dict:
    manifest = install.parent.parent / f"appmanifest_{APP_ID}.acf"
    build = "unknown"
    if manifest.is_file():
        match = re.search(r'"buildid"\s+"([^"]+)"', manifest.read_text(errors="replace"))
        if match:
            build = match[1]
    files = {}
    for relative in ("game/citadel/gameinfo.gi", "game/citadel/cfg/autoexec.cfg", "game/citadel/cfg/video.txt"):
        path = install / relative
        files[relative] = digest(path) if path.is_file() else None
    return {"build_id": build, "baseline_files": files}


def game_processes() -> dict[int, str]:
    """Only actual Deadlock executables, never Python/shell command strings.

    /proc starttime is recorded with each PID to prevent signaling PID reuse.
    """
    found = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().split(b"\0")
            executable = args[0].decode(errors="replace").replace("\\", "/").rsplit("/", 1)[-1].lower()
            if executable not in {"deadlock.exe", "deadlock", "citadel", "project8.exe"}:
                continue
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if stat[0] == "Z":
                continue
            found[int(proc.name)] = stat[19]
        except (OSError, IndexError):
            continue
    return found


def doctor(install: Path | None, workspace: Path) -> list[dict]:
    checks = []

    def add(name, passed, detail):
        checks.append({"check": name, "ok": bool(passed), "detail": str(detail)})

    add("Linux", platform.system() == "Linux", platform.system())
    add("Steam", shutil.which("steam"), shutil.which("steam") or "Install native Steam and sign in.")
    add("MangoHud", shutil.which("mangohud"), shutil.which("mangohud") or "Install MangoHud and its 32-bit package if needed.")
    add("Game install", install and (install / "game/citadel/gameinfo.gi").is_file(), install or "Use dpl init --install PATH.")
    add("Game closed", not game_processes(), "Close Deadlock before a suite. Existing games are never killed.")
    if install:
        add("Native Steam library", ".var/app/com.valvesoftware.Steam" not in str(install),
            "Flatpak Steam automation is not supported." if ".var/app/com.valvesoftware.Steam" in str(install) else "Native installation")
        guard = install_lock(install).with_suffix(".json")
        if guard.exists():
            pending = read_json(guard)
            state = read_json(Path(pending["journal"]))
            add("Install recovery", state.get("state") == "restored", f"Recovery workspace: {pending['workspace']}")
        add("Writable game config", os.access(install / "game/citadel/cfg", os.W_OK), install / "game/citadel/cfg")
    journals = [p for p in (workspace / "sessions").glob("*/runs/*/transaction.json")
                if '"state": "restored"' not in p.read_text()]
    add("Recovery", not journals, "No pending restores." if not journals else f"Run dpl recover; {len(journals)} journal(s).")
    return checks


def process_matches(pid: int, start_time: str) -> bool:
    """Check a known process without scanning every process during capture."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[0] != "Z" and fields[19] == start_time
    except (OSError, IndexError):
        return False
