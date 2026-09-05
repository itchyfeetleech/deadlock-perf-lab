# Faster configuration sweeps

Use a short screening pass to find candidates, then spend longer on confirmation. A GameInfo or renderer change needs a fresh game process; changing a startup-only cvar through the console is not an equivalent test.

## What changed in the runner

The prototype added a fixed 20-second pause after every replay load. The runner now waits for the engine's `Signon traffic "DEMO"` completion message and a one-second guard before seeking. It still waits for the seek to complete, warms the selected section, seeks back and captures the same configured duration.

If the expected ready signal never arrives, the run fails rather than measuring an incompletely loaded scene. Game shutdown polls for the owned process to exit; it does not always sleep the entire grace period. The capture file is finalized before its checksum and metrics are recorded.

## Screen a large matrix

```bash
# Quotes keep your shell from expanding profile selectors as filenames.
dpl plan --cases 'gi*' --preset screen --experimental
dpl run --live
dpl shortlist --top 5
```

`screen` uses one round, 10 seconds of sampling, 5 seconds of warm-up, 1 second of settle and no cooldown. One round of 50 treatments is 52 launches instead of 156 for three rounds. Results are provisional; one round cannot establish a directional verdict. It is possible to miss a small genuine effect in a short screen.

To generate one-variable GameInfo profiles from a CSV:

```bash
dpl profile sweep examples/convar-matrix.csv --base '/path/to/Deadlock/game/citadel/gameinfo.gi'
```

The CSV needs `id,cvar,value` columns, with optional `name`. Each generated profile changes one direct ConVars assignment in the supplied base; missing variables are added there. Duplicate definitions and unchanged values (including boolean aliases) are rejected. Before live planning, the recorded base hash must match your current GameInfo, so a baseline change cannot quietly turn a one-variable test into a multi-variable comparison. Inspect each generated file before enabling experimental runs. The example matrix contains hypotheses, not recommended settings.

## Confirm the shortlist

```bash
dpl plan --cases gi-example-a,gi-example-b --preset confirm --experimental
dpl run --live
```

`confirm` uses five rounds, 30-second samples, 45-second warm-up, 5-second settle and 5-second cooldown. The full duration and number of rounds are saved in the plan. A shortlist is ranked by measured average-FPS change; ranking does not waive drift, missing rounds, cvar, camera or data-quality checks.

If a change is too small to separate from noise, add independent rounds or choose a more representative scenario. Repeating all 50 treatments before a screening pass is usually an expensive way to discover no-op or ineffective changes.

## Inspect time spent

```bash
dpl timings SESSION_ID
```

This reports successful-run wall time, the configured sample length, progress and remaining-time estimates from completed iterations. Estimates apply to that machine and workload. Startup from a cold Steam client, shader work and unfamiliar maps can take longer than later iterations.

Use `--preset custom` (the default) to retain timings from `lab.json`, and `--rounds N` to override the count. Presets do not edit your saved workspace configuration. Comparing separate presets is not a valid A/B experiment because warm-up and sample conditions differ.

## Scout before screening

For a large set of hypotheses, `--preset scout` uses a 5-second sample, 2-second warm-up, 1-second settle and one round:

```bash
dpl plan --cases 'gi*' --preset scout --experimental
dpl run --live
dpl timings
dpl shortlist --top 5
```

This saves eight configured seconds per iteration compared with `screen`. Shorter windows are less representative and tail estimates are noisier; scouting can miss small effects or intermittent stalls. Confirm candidates with longer repeated captures. Do not compare a scouting capture directly with a baseline from a different preset.

New plans also use a 100 ms camera-command guard instead of a one-second guard, followed by the configured settle period. Existing frozen plans retain their old behavior. Live captures still require camera/playback review.

`dpl timings` now includes median phase durations for setup, launch, console connection, replay load, seeking, warm-up, camera/settle, sampling, shutdown, analysis and restoration. Phase medians need not sum to the median total. Older results lack phase measurements and are not assigned zero durations.

## Long Steam startup pauses

A local scouting test recorded a 50-second launch phase. Steam's `shader_log.txt` showed `fossilize_replay` processing Vulkan pipelines during that wait, before the game process appeared. The benchmark cannot remove that delay by shortening its own sleeps.

Allow shader preparation to finish before timing a suite, keep the same renderer and preserve the existing cache between trials. This does not guarantee that Steam will do no further preparation. Do not toggle shader pre-caching off and on to speed a benchmark: a [Valve maintainer explains that toggling resets the component and flushes locally built shaders](https://github.com/ValveSoftware/steam-for-linux/issues/8973). The runner does not change Steam's global cache settings or silently skip shader work.
