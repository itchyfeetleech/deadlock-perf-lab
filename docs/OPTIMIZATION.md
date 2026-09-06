# Testing configurations

Start with one change and the same replay scene. The baseline is your current installation, including existing configs. See the [first experiment guide](QUICKSTART.md) for capture setup.

## Built-in and custom profiles

`dpl profiles` lists FPS caps, renderer flags and community GameInfo snapshots. Inspect a profile before planning:

```bash
dpl profile show fps-unlock
dpl plan --cases fps-unlock --rounds 5
```

For a custom cvar:

```bash
printf 'fps_max 165\n' > cap165.cfg
dpl profile add cap-165 --autoexec cap165.cfg --description '165 FPS game cap'
dpl plan --cases cap-165 --rounds 5
```

Cvar profiles accept assignments and comments. Commands that load other configs, bind keys or change the scene are rejected. The source is copied into the profile and frozen in each plan. Readback checks confirm the requested value; inspect the game to check its actual effect.

Use [manual experiments](MANUAL_EXPERIMENTS.md) for video settings, resolution, upscaling, Proton, drivers or OS settings. Record visual differences as well as frame times. A cap can lower average FPS while improving pacing.

## Community GameInfo files

The bundled files are attributed snapshots from 2026-09-04. They change many variables and can reduce visual quality or break with game updates. Inspect the diff against your installation:

```bash
dpl profile show community-sqooky --diff
dpl plan --cases community-sqooky --rounds 5 --experimental
```

Whole-file swaps require `--experimental`. The tool restores your original files after the run. Source hashes and credits are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Screen a large set

Use short captures to find candidates, then confirm them in a fresh experiment with longer captures and repeated rounds.

| Preset | Rounds by default | Capture | Warm-up | Settle | Cooldown |
|---|---:|---:|---:|---:|---:|
| `scout` | 1 | 5 s | 2 s | 1 s | 0 s |
| `screen` | 1 | 10 s | 5 s | 1 s | 0 s |
| `confirm` | 5 | 30 s | 45 s | 5 s | 5 s |
| `custom` (default) | 5 | From `lab.json` | From `lab.json` | From `lab.json` | From `lab.json` |

`--rounds N` overrides the round count. Presets are saved in the plan without editing `lab.json`. Short passes can miss small effects and intermittent stalls; neither `scout` nor `screen` has enough rounds for an improvement verdict.

To generate one-cvar GameInfo profiles from a CSV:

```bash
dpl profile sweep examples/convar-matrix.csv --base '/path/to/Deadlock/game/citadel/gameinfo.gi'
dpl plan --cases 'gi*' --preset screen --experimental
dpl run --live
dpl shortlist --top 5
```

The CSV requires `id,cvar,value`, with an optional `name`. Each profile changes one direct ConVars assignment, or adds it if absent. Duplicate definitions and unchanged values are rejected. The base file must match your current GameInfo when you plan the live run. The [example matrix](../examples/convar-matrix.csv) contains candidates to test, not recommended settings. Quote selectors such as `'gi*'` to prevent shell expansion.

Inspect the shortlisted results, then use their profile IDs in a new plan:

```bash
dpl plan --cases gi-example-a,gi-example-b --preset confirm --experimental
dpl run --live
```

Rankings use average FPS change and do not override measurement checks. Compare each treatment with its own session's baselines; different presets use different capture conditions.

## Estimate runtime

```bash
dpl timings
```

This shows successful-run durations, phase medians and an estimate of remaining time. GameInfo and renderer changes require a fresh process. A one-round screen of 50 treatments means 52 launches, including the two baselines. Launching, loading and seeking take time beyond the preset durations.

Large launch delays can come from Steam shader preparation. Let it finish and keep the renderer and cache state consistent between trials. See [troubleshooting](TROUBLESHOOTING.md) for startup and capture failures.

New plans start replay loading from the temporary startup config and seek immediately after confirmed signon. Cvar readback and final demo-info requests use engine acknowledgements rather than fixed delays; hidden cvars remain flagged. Readback runs during the configured camera-settle interval. These changes reduce setup time while retaining the configured warm-up and capture duration. Create a fresh plan to use the new replay-start protocol; existing plans preserve their recorded scenario.

Repeated captures still launch a fresh process. Reusing a process for all five repetitions could save more launch/load time, but changes the independence and cache history of the experiment and is not supported by this runner. Replay seeking already uses the engine's fast-goto path when available; changing demo speed, cutting the replay file, or skipping warm-up can change the scene or cache state being measured.
