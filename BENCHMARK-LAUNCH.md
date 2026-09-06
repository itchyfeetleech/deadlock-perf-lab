# Restart the 100-CVAR teamfight benchmark

The completed three-repeat community screen is now in [the results page](cvar-impact.html). For the next **99-capture numeric experiment**, use [Numeric CVAR value sweep](docs/VALUE_SWEEP.md). The instructions below retain the earlier 505-capture restart recipe.

The original run was cancelled on request. Keep its partial measurements in `.lab/sessions/20260905T223956Z-339461`; do not reset its status or delete its results. Restarting below creates a **new 505-capture session from the beginning**, preserving the exact original profiles and schedule and recording the faster v3 replay-start protocol. The tool does not resume a cancelled session.

## Frozen experiment

- Replay: `replays/102565106.dem` in the installed Deadlock `game/citadel` directory.
- Capture begins from tick **134987**; **10 seconds** per capture.
- Warm-up: 10 seconds, then re-seek to 134987, pause, select player `1` / chase camera and settle for 2 seconds before resuming.
- 100 independent GameInfo CVAR changes, each repeated 5 times, plus 5 baseline captures: **505 total**.
- Priority: 65 CPU, 25 GPU, 10 exploratory UI/audio/streaming cases. Seed: 134987; shuffled within priority tiers each round.
- One baseline per round, progressively positioned at the start, quarter, middle, three quarters and end.
- Existing 1280×720 video settings, game build, baseline files and hardware context frozen in the original plan.
- Every capture uses a fresh game process and restores the previous config after completion or graceful cancellation.

The complete selected values and research references are in `.lab/research/teamfight100/matrix.csv` and its `README.md`. The original immutable `plan.json` contains the full profiles, exact schedule, replay hash and conditions. Nineteen selected baseline values were read back live; 81 hidden CVAR baseline values are provisional community definitions. Treatment readback failures remain visible in quality notes. This five-baseline design produces descriptive averages; the native tool's ten-baseline bracketed statistical verdict is not applicable.

## Prepare a new session (does not launch the game)

Run these commands from a terminal:

```bash
cd /home/hoppcx/Work/deadlock-perf-lab
PYTHONPATH=src python .lab/research/teamfight100/restart-plan.py
```

The helper upgrades replay startup to `source2-demo-signon-v3`: start from the temporary config and seek immediately after confirmed signon. CVAR readback uses acknowledged batches, overlaps camera settling, and no longer waits five seconds for hidden variables. Warm-up and the 10-second sample remain unchanged.

The helper checks that Deadlock is closed and the original game build, baseline files, system identity and replay hash still match. If they changed, review the experiment and regenerate it for the new conditions. It preserves the cancelled session and updates `session.txt` to the newly prepared session. Do not rerun `prepare.py`: its existing profile IDs are already installed.

## Launch the prepared session

Keep Steam running with its existing MangoHud launch options. Run:

```bash
cd /home/hoppcx/Work/deadlock-perf-lab
setsid -f env PYTHONPATH=src python -u .lab/research/teamfight100/run.py </dev/null >> .lab/research/teamfight100/benchmark.log 2>&1
```

Run the launch command once. The process is detached and continues after the terminal closes. Avoid manually launching another game instance or changing settings during the suite.

## Check progress

```bash
cd /home/hoppcx/Work/deadlock-perf-lab
tail -n 20 .lab/research/teamfight100/benchmark.log
cat .lab/research/teamfight100/session.txt
python - <<'PY'
from pathlib import Path
import json
session = Path(Path('.lab/research/teamfight100/session.txt').read_text())
print(json.dumps(json.loads((session / 'status.json').read_text()), indent=2))
PY
```

The session's `status.json` records progress. Results and raw captures stay inside its `runs` directory. On completion or graceful cancellation, the runner writes the native HTML report and `report/five-repeat-averages.csv`, with arithmetic means, baseline-relative FPS differences, capture counts and quality notes. Partial results show fewer than five repeats and must not be mistaken for a finished experiment.

## Cancel gracefully

```bash
cd /home/hoppcx/Work/deadlock-perf-lab
python - <<'PY'
from pathlib import Path
import os, signal
pid = int(Path('.lab/research/teamfight100/runner.pid').read_text())
cmdline = Path(f'/proc/{pid}/cmdline')
if cmdline.exists() and b'teamfight100/run.py' in cmdline.read_bytes():
    os.kill(pid, signal.SIGTERM)
    print('Graceful cancellation requested.')
else:
    print('The saved benchmark process is no longer running.')
PY
```

If cancellation arrives while Steam is still launching, cleanup waits for the pending game to appear (bounded by the 180-second launch deadline), stops it, and then restores files. Allow cleanup to finish, then run `PYTHONPATH=src python -m deadlock_perf_lab doctor` to check restoration. Do not use SIGKILL or kill the game separately. If an abrupt shutdown interrupted restoration, close Deadlock and use `PYTHONPATH=src python -m deadlock_perf_lab recover` before restarting.

## Resume after the 2026-09-06 crash

Session `20260905T230142Z-03850b` failed at 231/505: a one-off Proton `wineserver` SIGBUS race (`fsync_alloc_shm`) killed capture 232's game launch. Configs were restored on the way down; the partial session and its report remain untouched evidence.

On request the experiment was completed at **three captures per case** instead of five. `resume-plan.py` deep-copies the failed session's plan and keeps only the schedule items still needed to reach three ok captures per case when walking forward from the last completed item — items 232–303, the rest of round 3 including its baseline at index 253 — then re-signs the plan and prepares a fresh session (`resumed_from` records provenance). It applies the same checks as `restart-plan.py`: game closed, game build, system identity and replay unchanged. Prepare and launch it the same way:

```bash
cd /home/hoppcx/Work/deadlock-perf-lab
PYTHONPATH=src python .lab/research/teamfight100/resume-plan.py
# then the standard detached launch command above
```

The resumed session `20260906T014321Z-db841b` completed 72/72 on 2026-09-06, giving every case exactly three captures across the two sessions (303 ok runs total; the failed item 232 was re-run as the resume's first capture). Combined results: `.lab/research/teamfight100/three-repeat-averages.csv` and `three-repeat-summary.md`, written by `three-repeat-report.py`, which merges both sessions' ok runs and asserts their context keys and frozen profiles match. The two per-session native reports remain in their own session directories.

A combined native web report lives at `.lab/combined-tf100-3x/report/index.html` (built by `combined-report.py`: the frozen plan's first 303 schedule items plus full run directories copied byte-identical). The analyzer cannot pair rounds in this one-baseline-per-round design, so its FPS-change and rounds columns are empty natively; `fix-combined-report.py` patches that report in place with the descriptive three-repeat deltas (identical to the CSV) and actual capture rounds. Re-run the fix after any native regeneration of that report.
