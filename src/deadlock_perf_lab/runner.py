"""Serialized Linux runs, isolated captures, and guaranteed attempted recovery."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import math
import os
from pathlib import Path
import random
import re
import signal
import subprocess
import time

from .capture import read_mangohud
from .profiles import validate
from .storage import LabError, digest, exclusive_lock, read_json, write_json
from .system import APP_ID, doctor, game_identity, game_processes, identity, process_matches
from .transaction import Transaction
from .vconsole import VConsole
from .workspace import verify_plan


def install_lock(install: Path) -> Path:
    key = hashlib.sha256(str(install.resolve()).encode()).hexdigest()[:24]
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache / "deadlock-perf-lab/locks" / f"{key}.lock"


def emit(session: Path, message: str) -> None:
    print(message, flush=True)
    with (session / "events.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def stop_owned(processes: dict[int, str]) -> None:
    # Signal only still-matching executable + PID starttime identities.
    for sig, grace in ((signal.SIGTERM, 8), (signal.SIGKILL, 3)):
        alive = game_processes()
        for pid, start in processes.items():
            if alive.get(pid) == start:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            alive = game_processes()
            if not any(alive.get(pid) == start for pid, start in processes.items()):
                return
            time.sleep(.2)
    raise LabError("Game survived shutdown. Close it, then use dpl recover before running another benchmark.")


def pause(seconds: float, console: VConsole | None = None, processes: dict[int, str] | None = None) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if processes and not any(process_matches(pid, start) for pid, start in processes.items()):
            raise LabError("Deadlock exited before the measurement finished.")
        if console:
            lines = console.read(min(.2, max(0, deadline - time.monotonic())))
            if any("demo playback finished" in line.lower() or "demo ended" in line.lower() for line in lines):
                raise LabError("Replay ended during the measurement. Select an earlier tick.")
        else:
            time.sleep(min(.2, max(0, deadline - time.monotonic())))


def capture_file(directory: Path, timeout: float = 20) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = [p for p in directory.glob("*.csv") if "deadlock" in p.name.lower()
                      and not p.name.endswith("_summary.csv") and p.stat().st_size > 256]
        if len(candidates) > 1:
            raise LabError("Multiple Deadlock captures in a single run; capture identity is ambiguous.")
        if candidates:
            return candidates[0]
        time.sleep(.2)
    raise LabError("No Deadlock MangoHud log in this run's capture directory. Set the Steam launch options shown by dpl setup.")


def last_elapsed(path: Path) -> float:
    import csv
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 16384))
        tail = f.read().decode(errors="replace").splitlines()
    for line in reversed(tail[:-1]):  # last row could still be in flight
        try:
            fields = next(csv.reader([line]))
            value = float(fields[-1]) / 1e9
            if len(fields) >= 15 and math.isfinite(value) and value > 0:
                return value
        except (ValueError, IndexError):
            pass
    raise LabError("Cannot locate a complete MangoHud elapsed timestamp.")


def quote_console(value: str) -> str:
    if any(c in value for c in '\n\r\0;"'):
        raise LabError("Replay/camera names cannot contain quotes, semicolons or control characters.")
    return f'"{value}"'


def verify_assignments(console: VConsole, content: str) -> list[str]:
    blockers = []
    for line in content.splitlines():
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        name, expected = line.split(None, 1)
        expected = expected.strip().strip('"')
        console.drain()
        console.send(name)
        try:
            reply = console.wait_for(f"{name} =", 5)
            match = re.search(rf"\b{re.escape(name)}\s*=\s*([^\s\]]+)", reply)
            actual = match[1].strip('"') if match else ""
            aliases = {"true": "1", "false": "0"}
            actual, wanted = aliases.get(actual.lower(), actual), aliases.get(expected.lower(), expected)
            try:
                matches = math.isclose(float(actual), float(wanted), rel_tol=1e-5, abs_tol=1e-5)
            except ValueError:
                matches = actual == wanted
            if not matches:
                blockers.append(f"{name}: requested {expected}, read back {actual or 'unknown'}.")
        except LabError:
            blockers.append(f"{name}: no readback; this game build may ignore or reject the setting.")
    return blockers


def run_live(workspace: Path, session: Path, plan: dict, item: dict, directory: Path) -> dict:
    install = Path(plan["install"])
    scenario = plan["context"]["scenario"]
    profile = validate(plan["profiles"][item["case"]])
    if game_processes():
        raise LabError("Deadlock is already running. Close it first; this tool will not kill an existing game.")
    if game_identity(install) != plan["context"]["game"]:
        raise LabError("Game build or baseline files changed since planning. Create a new plan.")
    if identity() != plan["context"]["system"]:
        raise LabError("System identity changed since planning (kernel/hardware/governor). Create a new plan.")
    txn = Transaction(directory / "transaction.json")
    txn.data["install"] = str(install)
    txn.save()
    guard = install_lock(install).with_suffix(".json")
    write_json(guard, {"journal": str(txn.path), "workspace": str(workspace)})
    processes = {}
    console = None
    launched = False
    capture_dir = directory / "capture"
    capture_dir.mkdir()
    game_cfg = install / "game/citadel/cfg/autoexec_dpl.cfg"
    capture_config = workspace / "capture.conf"
    for target in (game_cfg, install / "game/citadel/gameinfo.gi"):
        if not target.resolve().is_relative_to(install.resolve()):
            raise LabError(f"Game config resolves outside the install: {target}")
    blockers = []
    warnings = []
    if any(v == "record me" for v in plan["context"]["conditions"].values()):
        blockers.append("Record resolution, graphics preset, Proton and display mode in lab.json before drawing conclusions.")
    try:
        content = profile.get("content", "") if profile["kind"] == "autoexec" else ""
        if scenario["mode"] == "bots":
            content += "\n" + files("deadlock_perf_lab").joinpath("assets/scenario_stress.cfg").read_text()
        txn.apply(game_cfg, ("// Temporary Deadlock Perf Lab configuration\n" + content).encode())
        if profile["kind"] == "gameinfo":
            txn.apply(install / "game/citadel/gameinfo.gi", profile["content"].encode())
            blockers.append("Whole GameInfo swap: file application verified, individual cvar effects and replay fidelity require review.")
        # Per-game Steam launch options read this at each fresh process launch.
        # No interval sampling and no fixed duration which might stop mid-load.
        # NOTE: no `no_display` here. MangoHud 0.8.4 only runs its autostart
        # check inside the overlay update path, which `no_display` skips
        # until logging is already active — autostart would never fire. The
        # small default HUD is identical in every run, so relative
        # comparisons are unaffected. (The neutral/manual configs keep
        # `no_display` because they never autostart.)
        txn.apply(capture_config, (f"log_interval=0\nlog_duration=0\nautostart_log=1\n"
                                   f"output_folder={capture_dir}\n").encode())
        args = ["steam", "-applaunch", APP_ID, "-insecure", "-dev", "-vconsole", "-condebug"]
        args += profile.get("flags", []) if profile["kind"] == "launch" else []
        args += ["+exec", "autoexec_dpl"]
        if scenario["mode"] == "bots":
            if not re.fullmatch(r"[A-Za-z0-9_]+", scenario["map"]):
                raise LabError("Map name must contain only letters, digits and underscores.")
            args += ["+map", scenario["map"]]
        env = os.environ.copy()
        env.pop("MANGOHUD_CONFIG", None)
        env.update(MANGOHUD="1", MANGOHUD_CONFIGFILE=str(capture_config))
        with (directory / "steam.log").open("wb") as output:
            subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             env=env, start_new_session=True)
        launched = True
        emit(session, "  Waiting for the game process.")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            processes = game_processes()
            if processes:
                txn.track_processes(processes)
                break
            time.sleep(.5)
        if not processes:
            raise LabError("Deadlock did not launch within 180s. Check Steam login and steam.log.")
        emit(session, "  Game process ready; connect to VConsole.")
        console = VConsole(directory / "vconsole.log")
        if scenario["mode"] == "replay":
            console.command_wait("playdemo " + quote_console(scenario["replay_command"]), "playing demo from")
            emit(session, "  Replay opened; wait for completed signon.")
            # The old fixed 20s delay was paid on every launch. Wait for
            # the engine's completed demo signon instead; seeking on the
            # earlier "playing demo" message can race initialization.
            console.wait_for('Signon traffic "DEMO"', 120)
            emit(session, "  Replay signon complete; prepare the capture window.")
            pause(scenario.get("load_guard_s", 1), console, processes)
            console.command_wait(f"demo_gototick {scenario['tick']}", f"Demo Skipping finished at tick {scenario['tick']}")
            emit(session, f"  Warm replay for {scenario['warmup_s']}s, then seek back to tick {scenario['tick']}.")
            pause(scenario["warmup_s"], console, processes)
            # Re-seek AFTER warming, so differing load times never move the
            # measurement window further into the match.
            console.send("demo_pause")
            console.command_wait(f"demo_gototick {scenario['tick']}", f"Demo Skipping finished at tick {scenario['tick']}")
            console.send("demo_pause")
            if scenario.get("player"):
                console.send("spec_player " + quote_console(str(scenario["player"])))
                pause(1, console, processes)
            else:
                warnings.append("Replay uses its default POV. Inspect the run before sharing; set scenario.player for an explicit target.")
                blockers.append("Replay POV is not explicitly selected.")
            console.send("spec_chase")
        else:
            console.wait_for("ChangeGameState: HeroSelection")
            for command in ("changeteam 1", "spec_autodirector 0", "spec_next"):
                console.send(command)
                pause(1, console, processes)
            console.send("spec_chase")
        console.send("sv_cheats 0")
        blockers += verify_assignments(console, "sv_cheats 0")
        if profile["kind"] == "autoexec":
            blockers += verify_assignments(console, profile["content"])
        pause(scenario["settle_s"], console, processes)
        capture = capture_file(capture_dir)
        if time.time() - capture.stat().st_mtime > 2:
            raise LabError("MangoHud stopped logging before sampling.")
        start = last_elapsed(capture)
        # Read demo_info before and after for human-verifiable playback
        # progression. Unknown/changed engine output blocks a verdict.
        console.drain()
        console.send("demo_info") if scenario["mode"] == "replay" else None
        if scenario["mode"] == "replay":
            console.send("demo_resume")
        emit(session, f"  Capture {scenario['sample_s']}s at per-frame resolution.")
        start_clock = time.monotonic()
        pause(scenario["sample_s"] + .3, console, processes)
        if scenario["mode"] == "replay":
            console.send("demo_pause")
            console.send("demo_info")
            pause(.5, console, processes)
            # Different builds expose different demo_info strings. Keep
            # both raw outputs and demand explicit verification for now.
            blockers.append("Replay progression and camera require operator review; demo_info describes the file, not current playback state.")
        # Finalize the raw log before parsing/hashing it; live CSV writers
        # otherwise change evidence after its digest was recorded.
        console.close()
        console = None
        processes.update(game_processes())
        txn.track_processes(processes)
        stop_owned(processes)
        launched = False
        processes = {}
        result_capture = read_mangohud(capture, start_s=start, duration_s=scenario["sample_s"], interval_ms=0)
        if result_capture.metadata["invalid_rows"]:
            blockers.append("The raw capture contained malformed rows; inspect before drawing conclusions.")
        write_json(directory / "window.json", {"start_elapsed_s": start, "duration_s": scenario["sample_s"],
                                                "wall_measurement_s": time.monotonic() - start_clock,
                                                "capture_name": capture.name})
        from .report import chart_series
        result = {"metrics": result_capture.metrics(1000 / scenario["budget_fps"]),
                  "capture_sha256": result_capture.metadata["sha256"], "raw_capture": str(capture.relative_to(directory)), "capture_metadata": result_capture.metadata,
                  "series": chart_series(result_capture.times, result_capture.frames),
                  "warnings": warnings + result_capture.warnings, "quality_blockers": blockers}
        if profile["kind"] == "launch":
            result["quality_blockers"].append("Renderer flag requested; verify the selected API in steam.log or the game overlay.")
        return result
    finally:
        if console:
            console.close()
        # No game existed before launch, and install-wide locking prevents
        # another lab from launching one. Catch late processes on error paths.
        if launched:
            processes.update(game_processes())
            txn.track_processes(processes)
            stop_owned(processes)
        txn.restore()
        guard.unlink(missing_ok=True)


def run_demo(plan: dict, item: dict, directory: Path) -> dict:
    seed = int(hashlib.sha256(f"{plan['seed']}:{item['index']}:{item['case']}".encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    factor = {"baseline": 1, "fps-unlock": 1.08, "cap-144": .6, "cap-240": .99,
              "renderer-vulkan": 1.05, "renderer-dx11": .98}.get(item["case"], 1.12)
    baseline_ms = 1000 / (240 * factor * rng.uniform(.995, 1.005))
    elapsed = 0.0
    duration = plan["context"]["scenario"]["sample_s"]
    path = directory / "capture.csv"
    with path.open("w", encoding="utf-8") as f:
        f.write("os,cpu,gpu,ram,kernel,driver,cpuscheduler\nDEMO,Illustrative CPU,Illustrative GPU,0,DEMO,DEMO,DEMO\n")
        f.write("fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,gpu_core_clock,gpu_mem_clock,gpu_vram_used,gpu_power,ram_used,swap_used,process_rss,cpu_mhz,elapsed\n")
        i = 0
        while elapsed < duration + .5:
            frame = baseline_ms * max(.2, rng.gauss(1, .1))
            if i and i % 751 == 0:
                frame += rng.uniform(14, 25)
            elapsed += frame / 1000
            f.write(f"{1000/frame:.6f},{frame:.6f},38,65,85,62,59,2400,2000,5.4,180,11,0,0,4500,{elapsed*1e9:.0f}\n")
            i += 1
    capture = read_mangohud(path, duration_s=duration, interval_ms=0)
    from .report import chart_series
    return {"metrics": capture.metrics(1000 / plan["context"]["scenario"]["budget_fps"]),
            "capture_sha256": capture.metadata["sha256"], "raw_capture": "capture.csv", "capture_metadata": capture.metadata,
            "series": chart_series(capture.times, capture.frames),
            "warnings": ["DEMO DATA — synthetic capture."], "quality_blockers": []}


@contextlib.contextmanager
def interruptible():
    old = signal.getsignal(signal.SIGTERM)

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, old)


def run_session(workspace: Path, session: Path) -> None:
    plan = read_json(session / "plan.json")
    verify_plan(plan)
    if plan.get("manual"):
        raise LabError("Manual plans accept captures through dpl import; they do not launch the game.")
    if read_json(session / "status.json")["state"] != "planned":
        raise LabError("This session already started. Create a new plan; partial sessions remain available for inspection.")
    lock = workspace / ".operation.lock" if plan["synthetic"] else install_lock(Path(plan["install"]))
    with exclusive_lock(lock), interruptible():
        if not plan["synthetic"]:
            guard = lock.with_suffix(".json")
            if guard.exists():
                pending = read_json(guard)
                state = read_json(Path(pending["journal"]))
                if state.get("state") != "restored":
                    raise LabError(f"An earlier run needs recovery: dpl --workspace {pending['workspace']} recover")
                guard.unlink()
            failures = [c for c in doctor(Path(plan["install"]), workspace) if not c["ok"]]
            if failures:
                raise LabError("Preflight failed: " + "; ".join(f"{c['check']}: {c['detail']}" for c in failures))
            scenario = plan["context"]["scenario"]
            if scenario["mode"] == "replay" and digest(Path(scenario["replay"])) != scenario["replay_sha256"]:
                raise LabError("Replay changed since planning.")
        total = len(plan["schedule"])
        completed = 0
        try:
            for item in plan["schedule"]:
                directory = session / "runs" / f"{item['index']:03d}-{item['case']}"
                directory.mkdir(parents=True, exist_ok=False)
                write_json(session / "status.json", {"state": "running", "completed": completed, "total": total, "current": item})
                emit(session, f"[{item['index']}/{total}] Round {item['round']} · {item['case']}" + (" · DEMO" if plan["synthetic"] else ""))
                record = {"schema": 1, "id": directory.name, **item, "context_key": plan["context_key"],
                          "synthetic": plan["synthetic"], "profile_sha256": plan["profiles"][item["case"]]["sha256"], "started_at": datetime.now(timezone.utc).isoformat()}
                try:
                    result = run_demo(plan, item, directory) if plan["synthetic"] else run_live(workspace, session, plan, item, directory)
                    record.update(result, status="ok")
                except BaseException as exc:
                    record.update(status="cancelled" if isinstance(exc, KeyboardInterrupt) else "failed", error=str(exc) or "Interrupted")
                    raise
                finally:
                    record["finished_at"] = datetime.now(timezone.utc).isoformat()
                    write_json(directory / "result.json", record)
                completed += 1
                emit(session, f"  {record['metrics']['avg_fps']:.1f} FPS · p99 {record['metrics']['p99_frame_ms']:.2f} ms")
                if not plan["synthetic"] and completed < total:
                    pause(plan["context"]["scenario"]["cooldown_s"])
            write_json(session / "status.json", {"state": "complete", "completed": completed, "total": total})
        except BaseException as exc:
            write_json(session / "status.json", {"state": "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed",
                                                 "completed": completed, "total": total, "error": str(exc) or "Interrupted"})
            raise


def recover(workspace: Path, *, force: bool = False) -> list[str]:
    restored = []
    if game_processes():
        raise LabError("Close Deadlock before recovery; restoring config under a live game is unsafe.")
    for path in sorted((workspace / "sessions").glob("*/runs/*/transaction.json")):
        transaction = Transaction(path)
        if transaction.data["state"] == "restored":
            continue
        install = Path(transaction.data.get("install", workspace))
        with exclusive_lock(install_lock(install)):
            if game_processes():
                raise LabError("Deadlock started during recovery. Close it and retry.")
            transaction.restore(force=force)
            guard = install_lock(install).with_suffix(".json")
            if guard.exists() and read_json(guard).get("journal") == str(path):
                guard.unlink()
            restored.append(str(path))
    return restored
