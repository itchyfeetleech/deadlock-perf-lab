# Numeric CVAR value sweep

Prepared at Sqooky's request after the 100-CVAR screen. This tests eight numeric CVARs at four candidate values each, independently: **32 variants × 3 repeats + 3 baselines = 99 captures**. It is prepared only; no game is launched by the preparation script.

| CVAR | Reference value* | Candidate values | Reason to test |
|---|---:|---|---|
| `cl_particle_fallback_base` | 0 | 2, 5, 10, 20 | Base setting for cheaper particle effects under load. |
| `cl_particle_fallback_multiplier` | 0 | 2, 5, 10, 20 | Scales fallback behavior; requested by Sqooky. |
| `cl_particle_sim_fallback_threshold_ms` | 6 | 1, 2, 4, 8 | Simulation-time threshold for new systems to use cheaper effects. |
| `cl_particle_sim_fallback_base_multiplier` | 5 | 1, 10, 25, 100 | How aggressively simulation overload triggers cheaper effects. |
| `r_particle_max_size_cull` | 1200 | 600, 900, 1600, 2400 | CPU/GPU tradeoff: systems larger in every dimension skip culling; lower values can save CPU checks while drawing more. |
| `r_size_cull_threshold` | 0.8 | 0.4, 1.0, 1.6, 2.4 | Strongest positive result in the screen: 1.6 averaged +6.66% FPS. |
| `cl_particle_max_count` | 0 | 250, 500, 1000, 2000 | 500 averaged −9.22% FPS; check whether the response changes with the count setting. |
| `lb_sun_csm_size_cull_threshold_texels` | 10 | 5, 20, 30, 60 | Numeric shadow-culling candidate; 30 averaged +2.07% FPS. |

*Reference values are provisional defaults from the community CVAR definitions, not independently verified live readbacks for these hidden settings. The actual reference configuration is the complete installed GameInfo at planning time, with existing video and autoexec settings. The common baseline covers the reference point; candidate values do not include unchanged default copies. These are test values, not recommended settings or proven safe visual limits.

The candidate definitions and particle-size interpretation come from [OptimizationLock's CVAR reference](https://github.com/Sqooky/OptimizationLock/blob/main/cvars_we_can_modify.txt) and [its base config](https://github.com/Sqooky/OptimizationLock/blob/main/Sqooky's%20.gi/base_convars.txt). Historical effects are exploratory arithmetic means from [the three-repeat screen](../results/teamfight100-three-repeat.csv).

Keep the same replay scene: demo `102565106.dem`, tick **134987**, player **1**, 10-second captures, 10-second warm-up, 2-second camera settling and no cooldown. The preparation script uses the replay configured in `.lab/lab.json` and explicitly freezes those timings and tick. Each variant changes one direct GameInfo ConVars assignment; each capture restarts the game and restores its original files. Order is seeded and shuffled each round, with the three baselines at the beginning, middle and end of their respective rounds.

Fallback controls may interact or remain inactive unless the workload crosses a threshold. A flat result does not prove a CVAR is useless. Do not combine candidates in this first pass. Afterward, compare all three captures, FPS, slow frames, readback quality and visual cues; use a separate confirmation experiment for the best candidate values or fallback combinations. Object/shadow culling can remove useful visual detail. These three-repeat averages are exploratory, with no bracketed statistical verdict.

## Prepare

From the repository root, with the tool installed (or `PYTHONPATH=src`):

```bash
PYTHONPATH=src python scripts/prepare_value_sweep.py
```

This reads [the value matrix](../examples/particle-value-matrix.csv), creates/reuses identical one-CVAR profiles, freezes a new plan and writes its path to `.lab/research/particle-values/session.txt`. It does not change the live game configuration or overwrite prior sessions. A prepared session already exists in this workstation's workspace; use its pointer instead of preparing again unless you want a new experiment.

## Launch later

With Steam running and Deadlock closed:

```bash
session=$(cat .lab/research/particle-values/session.txt)
setsid -f env PYTHONPATH=src python -u -m deadlock_perf_lab run "$session" --live </dev/null >> .lab/research/particle-values/benchmark.log 2>&1
```

At the measured ~37 seconds per iteration, estimate about **one hour**, plus variable Steam shader preparation. Monitor `.lab/research/particle-values/benchmark.log` and the session's `status.json`.

On completion, the native report contains each variant's mean metrics. To export a compact table grouped by CVAR/value and compared with the baseline mean:

```bash
PYTHONPATH=src python scripts/value_sweep_summary.py
```

The output is `report/value-sweep-averages.csv` inside the prepared session. It preserves counts and quality notes so incomplete or unverified candidates are visible. It does not automatically label a candidate as the best value.
