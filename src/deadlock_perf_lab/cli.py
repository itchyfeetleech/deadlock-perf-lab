"""One entry point for setup, experiments, analysis, recovery and sharing."""
from __future__ import annotations

import argparse
import csv
import difflib
import json
from pathlib import Path
import sys
import webbrowser

from . import __version__
from .analysis import analyze
from .capture import read_mangohud
from .imports import import_capture, review_run
from .planning import shortlist, timings
from .profiles import add_profile, catalog
from .report import bundle, generate_report, markdown_report
from .runner import recover, run_session
from .storage import LabError, atomic_write, digest, read_json
from .sweep import create_sweep
from .system import discover_install, doctor, identity
from .workspace import initialize, launch_options, load_workspace, make_plan, session_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dpl", description="Deadlock Perf Lab — Linux benchmark tools.",
                                epilog="Start with: dpl demo --open   |   dpl init   |   dpl guide")
    p.add_argument("--version", action="version", version=f"Deadlock Perf Lab {__version__}")
    p.add_argument("--workspace", type=Path, default=Path(".lab"), help="experiment workspace (default: .lab)")
    sub = p.add_subparsers(dest="command")

    def command(name, help_text):
        cmd = sub.add_parser(name, help=help_text, description=help_text)
        cmd.add_argument("--workspace", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        return cmd

    init = command("init", "Create a workspace; discover your Steam library.")
    init.add_argument("--install", help="Deadlock installation directory")
    init.add_argument("--replay", help="absolute or citadel-relative .dem path")
    diag = command("doctor", "Check game, tools, running processes and pending recovery.")
    diag.add_argument("--json", action="store_true")
    setup = command("setup", "Show the per-game Steam launch options for capture.")
    setup.add_argument("--manual", action="store_true", help="write a manual per-frame capture config (toggle with Shift+F2)")
    profiles = command("profiles", "List built-in and custom treatments.")
    profiles.add_argument("--json", action="store_true")
    profile = command("profile", "Inspect a treatment or add a frozen custom profile.")
    ps = profile.add_subparsers(dest="action", required=True)
    show = ps.add_parser("show")
    show.add_argument("id")
    show.add_argument("--diff", action="store_true", help="diff a GameInfo snapshot against the current install")
    sweep = ps.add_parser("sweep", help="create one-cvar GameInfo variants from id,cvar,value CSV")
    sweep.add_argument("matrix", type=Path)
    sweep.add_argument("--base", type=Path, required=True)
    add = ps.add_parser("add")
    add.add_argument("id")
    add.add_argument("--name")
    add.add_argument("--description", required=True)
    types = add.add_mutually_exclusive_group(required=True)
    types.add_argument("--autoexec", type=Path)
    types.add_argument("--gameinfo", type=Path)
    types.add_argument("--manual", action="store_true")
    plan = command("plan", "Freeze profiles, conditions and randomized baseline-bracketed rounds.")
    plan.add_argument("--cases", default="fps-unlock", help="comma-separated profile IDs")
    plan.add_argument("--rounds", type=int, help="default: 1 for screen, 5 otherwise")
    plan.add_argument("--preset", choices=["screen", "confirm", "custom"], default="custom", help="screen: 10s/one round; confirm: 30s/five rounds; custom: lab.json timings")
    plan.add_argument("--seed", type=int, default=47)
    plan.add_argument("--experimental", action="store_true", help="allow whole GameInfo treatments after inspection")
    plan.add_argument("--manual", action="store_true", help="plan captures made by the operator")
    run = command("run", "Execute an existing plan; --live is required for game launches.")
    run.add_argument("session", nargs="?", default="latest")
    run.add_argument("--live", action="store_true")
    demo = command("demo", "Exercise the full pipeline with conspicuously synthetic data; no game needed.")
    demo.add_argument("--open", action="store_true")
    demo.add_argument("--rounds", type=int, default=5)
    timing = command("timings", "Show observed iteration time and estimated remaining duration.")
    timing.add_argument("session", nargs="?", default="latest")
    short = command("shortlist", "Rank provisional screening candidates for a fresh confirmation experiment.")
    short.add_argument("session", nargs="?", default="latest")
    short.add_argument("--top", type=int, default=5)
    command("sessions", "Show experiment status and session IDs.")
    status = command("status", "Show a session's current progress.")
    status.add_argument("session", nargs="?", default="latest")
    inspect = command("inspect", "Inspect a MangoHud CSV without adding it to an experiment.")
    inspect.add_argument("csv", type=Path)
    inspect.add_argument("--interval-ms", type=float)
    inspect.add_argument("--start", type=float, default=0)
    inspect.add_argument("--duration", type=float)
    inspect.add_argument("--budget-fps", type=float, default=144)
    imp = command("import", "Import the next capture in a manual plan's frozen schedule.")
    imp.add_argument("csv", type=Path)
    imp.add_argument("--session", default="latest")
    imp.add_argument("--case", required=True)
    imp.add_argument("--round", type=int, required=True)
    imp.add_argument("--interval-ms", type=float, required=True, help="0 for confirmed per-frame logs; 100 for legacy 10Hz logs")
    imp.add_argument("--start", type=float, default=0)
    review = command("review", "Record an operator's scene/setting verification for one real run.")
    review.add_argument("session", nargs="?", default="latest")
    review.add_argument("--run", required=True)
    review.add_argument("--note", required=True)
    for name, description in (("compare", "Print baseline comparisons with uncertainty and quality gates."),
                              ("report", "Build an interactive offline HTML report, CSV, JSON and Markdown."),
                              ("export", "Create a shareable report ZIP; excludes raw captures, logs and backups.")):
        cmd = command(name, description)
        cmd.add_argument("session", nargs="?", default="latest")
        cmd.add_argument("--threshold", type=float, default=3)
        if name == "report":
            cmd.add_argument("--open", action="store_true")
        if name == "export":
            cmd.add_argument("--output", type=Path, required=True)
    rec = command("recover", "Restore pending transactions after a crash; verify original checksums.")
    rec.add_argument("--force", action="store_true", help="preserve conflicting edits then restore the verified backup")
    legacy = command("audit-legacy", "Inspect old results.csv without treating it as validated new evidence.")
    legacy.add_argument("csv", type=Path)
    command("guide", "Show the recommended measurement and optimization workflow.")
    return p


def show_plan(session: Path, plan: dict) -> None:
    print(f"\nExperiment {plan['id']} · {'MANUAL' if plan.get('manual') else 'DEMO' if plan['synthetic'] else 'LIVE PLAN'}")
    print(f"Preset: {plan.get('preset', 'custom')}\n{plan['rounds']} rounds · {len(plan['schedule'])} runs · seed {plan['seed']}")
    for round_index in range(1, plan["rounds"] + 1):
        print(f"  Round {round_index}: " + " → ".join(x["case"] for x in plan["schedule"] if x["round"] == round_index))
    s = plan["context"]["scenario"]
    minimum = len(plan["schedule"]) * (s["sample_s"] + s["warmup_s"] + s["settle_s"] + s["cooldown_s"]) / 60
    print(f"\nConfigured timing: about {minimum:.0f} minutes plus launch/load/seek overhead.")
    print(f"Frozen plan: {session / 'plan.json'}")
    print("Import captures in this order with dpl import." if plan.get("manual") else f"Execute: dpl --workspace {session.parent.parent} run {plan['id']} --live")


def guide() -> None:
    print("""DEADLOCK PERF LAB — Linux benchmark tools.

1. Try `dpl demo --open` to see the complete workflow without launching a game.
2. Run `dpl init`, then record resolution, graphics preset, Proton, display mode
   and replay/camera in .lab/lab.json. Baseline means YOUR current setup.
3. Run `dpl doctor` and `dpl setup`. Paste the displayed launch options into
   Deadlock's Steam Properties → General → Launch Options, retaining any
   unrelated options. Captures need MangoHud log_interval=0 (one row per frame).
4. Inspect `dpl profiles` and `dpl profile show ID`. Change one thing per trial.
   Start with FPS caps or renderers. Whole community GameInfo swaps are
   experimental, change many variables, and may reduce visibility or break replays.
5. `dpl plan --cases fps-unlock --rounds 5`, inspect the frozen plan, then
   `dpl run --live`. Close the game first. Ctrl+C cancels and attempts restoration.
6. `dpl report --open`. Check baseline drift, confidence intervals, slow frames,
   and actual in-game effects. Record operator checks with `dpl review`.
7. Confirm promising changes in a fresh experiment. `dpl export --output report.zip`
   shares only reports. Read labels/notes before sharing; raw logs stay local.

For video settings, upscaling, VRR/VSync, driver options, power profiles or Proton:
add a `dpl profile add ID --manual --description ...`, create a `dpl plan --manual`,
use `dpl setup --manual`, then capture/import each scheduled run. Apply and undo
those settings yourself between runs. The suite does not change your OS settings.

If interrupted by a crash or power loss: close Deadlock and run `dpl recover`.
Network settings affect a different measurement: FPS does not measure ping,
input latency, hit registration or competitive visibility.

Full guides: https://github.com/itchyfeetleech/deadlock-perf-lab/tree/main/docs
""")


def interactive() -> list[str]:
    print("\n  DEADLOCK PERF LAB\n  Linux benchmark tools.\n")
    choices = [("Try the demo and open the report", ["demo", "--open"]),
               ("Create a workspace", ["init"]), ("Check my setup", ["doctor"]),
               ("Browse benchmark profiles", ["profiles"]), ("Read the workflow", ["guide"]),
               ("Open the latest report", ["report", "--open"])]
    for i, (name, _) in enumerate(choices, 1):
        print(f"  {i}. {name}")
    answer = input("\nChoose 1–6 (Enter to exit): ").strip()
    if not answer:
        return []
    if not answer.isdigit() or not 1 <= int(answer) <= len(choices):
        raise LabError("Choose a number from 1 to 6.")
    return choices[int(answer) - 1][1]


def main(argv: list[str] | None = None) -> int:
    p = parser()
    try:
        args = p.parse_args(argv)
        if not args.command:
            if sys.stdin.isatty():
                selection = interactive()
                if selection:
                    return main(["--workspace", str(args.workspace), *selection])
            else:
                p.print_help()
            return 0
        workspace = args.workspace.expanduser().resolve()
        if any(c in str(workspace) for c in "\r\n,="):
            raise LabError("Workspace path cannot contain newlines, commas or '=' (MangoHud config syntax).")
        cmd = args.command
        if cmd == "init":
            initialize(workspace, args.install, args.replay)
            print(f"Workspace created: {workspace}\nEdit {workspace / 'lab.json'} to record your conditions.\nNext: dpl doctor · dpl setup · dpl guide")
        elif cmd == "doctor":
            config = read_json(workspace / "lab.json") if (workspace / "lab.json").exists() else {}
            install = Path(config["install"]) if config.get("install") else discover_install()
            checks = doctor(install, workspace)
            if args.json:
                print(json.dumps({"checks": checks, "system": identity()}, indent=2))
            else:
                for check in checks:
                    print(f"{'PASS' if check['ok'] else 'FAIL'}  {check['check']}: {check['detail']}")
                print("Steam launch-option wiring is verified by a fresh capture during the first live run.")
            return 0 if all(c["ok"] for c in checks) else 1
        elif cmd == "setup":
            load_workspace(workspace)
            options = launch_options(workspace)
            if args.manual:
                path = workspace / "manual.conf"
                atomic_write(path, f"log_interval=0\nautostart_log=0\noutput_folder={workspace / 'imports'}\n".encode())
                options = options.replace("capture.conf", "manual.conf")
            print("Deadlock → Steam Properties → General → Launch Options\n\n" + options)
            print("\nKeep any unrelated existing launch options. The suite does not edit Steam preferences.")
            print("Toggle manual logging with Shift+F2. Stop logging before importing." if args.manual else "Run dpl plan, then dpl run --live. Outside a run this config disables logging.")
        elif cmd == "profiles":
            entries = catalog(workspace)
            if args.json:
                print(json.dumps([{k: v for k, v in x.items() if k != "content"} for x in entries.values()], indent=2))
            else:
                for entry in entries.values():
                    print(f"{entry['id']:<23} {entry['kind']:<9} {entry.get('name', entry['id'])}\n  {entry['description']}")
        elif cmd == "profile":
            if args.action == "show":
                entry = catalog(workspace).get(args.id)
                if not entry:
                    raise LabError("Unknown profile. See dpl profiles.")
                print(json.dumps({k: v for k, v in entry.items() if k != "content"}, indent=2))
                if args.diff and entry["kind"] == "gameinfo":
                    config = load_workspace(workspace)
                    original = Path(config["install"]) / "game/citadel/gameinfo.gi"
                    print("".join(difflib.unified_diff(original.read_text().splitlines(True), entry["content"].splitlines(True),
                                                       fromfile="current/gameinfo.gi", tofile=args.id)))
                elif "content" in entry:
                    print(entry["content"])
            elif args.action == "sweep":
                load_workspace(workspace)
                paths = create_sweep(workspace, args.base, args.matrix)
                print(f"Created {len(paths)} one-cvar GameInfo profiles. Inspect them before an experimental run.")
                print("\n".join(str(path) for path in paths))
            else:
                load_workspace(workspace)
                kind = "autoexec" if args.autoexec else "gameinfo" if args.gameinfo else "manual"
                entry = {"id": args.id, "name": args.name or args.id, "kind": kind, "category": "custom",
                         "status": "experimental", "description": args.description}
                source = args.autoexec or args.gameinfo
                if source:
                    entry["content"] = source.read_text(encoding="utf-8")
                    entry["source_sha256"] = digest(source)
                print(add_profile(workspace, entry))
        elif cmd == "plan":
            session, plan = make_plan(workspace, args.cases.split(","), args.rounds if args.rounds is not None else (1 if args.preset == "screen" else 5), args.seed,
                                      experimental=args.experimental, manual=args.manual, preset=args.preset)
            show_plan(session, plan)
        elif cmd == "run":
            session = session_path(workspace, args.session)
            plan = read_json(session / "plan.json")
            if not plan["synthetic"] and not args.live:
                show_plan(session, plan)
                print("\nPlan only. Add --live to launch the game and apply temporary treatments.")
                return 0
            try:
                run_session(workspace, session)
            finally:
                if (session / "runs").exists():
                    print(f"Report: {generate_report(session)}")
        elif cmd == "demo":
            if not (workspace / "lab.json").exists():
                initialize(workspace)
            session, plan = make_plan(workspace, ["fps-unlock", "renderer-vulkan", "cap-144"], args.rounds, 47, demo=True)
            run_session(workspace, session)
            output = generate_report(session)
            print(f"\nDEMO DATA ONLY — no game was launched.\nReport: {output}")
            if args.open:
                webbrowser.open(output.as_uri())
        elif cmd == "timings":
            data = timings(session_path(workspace, args.session))
            print(json.dumps(data, indent=2))
        elif cmd == "shortlist":
            if not 1 <= args.top <= 50:
                raise LabError("top must be between 1 and 50")
            session = session_path(workspace, args.session)
            candidates = shortlist(session, args.top)
            print("Provisional candidates for retesting; this ranking does not confirm a benefit.")
            for c in candidates:
                print(f"  {c['case']:<28} {c['delta_pct']:+.2f}% average FPS · {len(c['paired_rounds'])} complete rounds · {c['verdict']}")
            if candidates:
                print("\nCreate a fresh confirmation plan:\ndpl plan --preset confirm --experimental --cases " + ",".join(c["case"] for c in candidates))
            else:
                print("No complete baseline-bracketed rounds yet.")
        elif cmd == "sessions":
            if not (workspace / "sessions").exists():
                print("No workspace yet. Start with dpl init or dpl demo.")
            else:
                for session in sorted((workspace / "sessions").iterdir()):
                    if (session / "status.json").exists():
                        status = read_json(session / "status.json")
                        print(f"{session.name}  {status['state']:<10} {status['completed']}/{status['total']}")
        elif cmd == "status":
            print(json.dumps(read_json(session_path(workspace, args.session) / "status.json"), indent=2))
        elif cmd == "inspect":
            import math
            if not math.isfinite(args.budget_fps) or args.budget_fps <= 0:
                raise LabError("budget-fps must be finite and positive.")
            capture = read_mangohud(args.csv, start_s=args.start, duration_s=args.duration, interval_ms=args.interval_ms)
            print(json.dumps({"metrics": capture.metrics(1000 / args.budget_fps), "metadata": capture.metadata, "warnings": capture.warnings}, indent=2))
        elif cmd == "import":
            print(import_capture(session_path(workspace, args.session), args.csv, args.case, args.round,
                                 interval_ms=args.interval_ms, start_s=args.start))
        elif cmd == "review":
            print(review_run(session_path(workspace, args.session), args.run, args.note))
        elif cmd in {"compare", "report", "export"}:
            session = session_path(workspace, args.session)
            if cmd == "compare":
                print(markdown_report(analyze(session, args.threshold)))
            elif cmd == "report":
                output = generate_report(session, args.threshold)
                print(output)
                if args.open:
                    webbrowser.open(output.as_uri())
            else:
                print(bundle(session, args.output.resolve(), args.threshold))
        elif cmd == "recover":
            restored = recover(workspace, force=args.force)
            print("\n".join(restored) if restored else "No pending restoration.")
        elif cmd == "audit-legacy":
            with args.csv.open(newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            synthetic = sum(r.get("synthetic", "").lower() == "true" for r in rows)
            sources = [r.get("mangohud_csv") for r in rows if r.get("mangohud_csv")]
            print(f"Legacy rows: {len(rows)} · synthetic: {synthetic} · reused CSV names: {len(sources) - len(set(sources))}")
            print("Legacy aggregate rows lack a verified measurement window and complete conditions.\nThey are historical observations; they are not imported into current experiments.\nUse dpl inspect on individual raw CSVs with their real --interval-ms and known time window.")
        elif cmd == "guide":
            guide()
        return 0
    except KeyboardInterrupt:
        print("\nCancelled. Restoration was attempted; run dpl doctor to check recovery state.", file=sys.stderr)
        return 130
    except (LabError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"dpl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
