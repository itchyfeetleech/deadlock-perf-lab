# Test settings you change yourself

Use manual experiments for in-game video settings, upscaling, frame caps outside the game, VRR/VSync, display modes, Proton, driver options and OS power settings. The application does not edit these settings for you. Make reversible changes, record the exact state and restore the control setup for each baseline.

## Prepare one treatment

```bash
dpl init  # only if you do not already have a workspace
dpl profile add shadows-low --manual --description 'Change shadow quality from High to Low; all other video settings unchanged'
```

Edit `.lab/lab.json` with the baseline conditions and the intended scenario, timing and frame budget. Record driver/Mesa version, Proton, resolution, render scale, VSync/VRR, display mode, overlays and background load. Set `sample_s` to your intended window, usually 30 seconds.

```bash
dpl plan --manual --cases shadows-low --rounds 5
dpl setup --manual
```

The printed schedule defines the capture order. With one treatment each round is baseline → shadows-low → baseline. A frozen manual plan accepts only imports; it cannot launch an automated suite. The setup command writes `manual.conf` in the workspace and prints the per-game Steam wrapper. Manual logging uses `log_interval=0`, is off at startup and writes into `.lab/imports/`.

## Capture each scheduled trial

1. Set the scheduled baseline or treatment. Restart the game when the setting needs a restart.
2. Warm the same scene and establish the same camera. For replay work, seek back to your intended starting point after warming.
3. Press **Shift+F2** (MangoHud's default logging toggle) to start. Capture at least the planned duration, then toggle it off. MangoHud hotkeys can be overridden by your configuration; see the [official configuration](https://github.com/flightlessmango/MangoHud/blob/master/data/MangoHud.conf).
4. Preserve a separate CSV for each trial. Complete repeat rounds independently; do not split one CSV into “repeats.”
5. Inspect and import the stopped log. If the actual measurement begins 2 seconds into the file, pass `--start 2`; the parser requires enough coverage for the complete planned duration.

```bash
dpl inspect .lab/imports/deadlock_FIRST.csv --interval-ms 0 --start 0 --duration 30
dpl import .lab/imports/deadlock_FIRST.csv --case baseline --round 1 --interval-ms 0
dpl import .lab/imports/deadlock_SECOND.csv --case shadows-low --round 1 --interval-ms 0
dpl import .lab/imports/deadlock_THIRD.csv --case baseline --round 1 --interval-ms 0
```

Continue with rounds 2–5. Follow the actual schedule when testing multiple treatments. Changed capture hardware metadata or logging intervals, repeated source hashes and wrong-order imports are rejected. A copy is stored per run; changing the original later does not change the experiment's evidence.

## Confirm conditions and interpret

An imported CSV cannot establish which settings or camera were active. Record a specific operator review for each capture you checked:

```bash
dpl review --run 002-shadows-low --note 'Confirmed Low shadows, same replay tick and player POV, and the unchanged baseline settings shown in my notes.'
dpl report --open
```

Reviews are bound to the exact result hash. They cannot waive bad data or missing pre-recorded conditions. Missing, malformed, sampled or unverified evidence produces inconclusive comparisons, not optimistic guesses. Reports summarize available CPU/GPU telemetry to support investigation, but low GPU load alone does not prove a CPU bottleneck.

To return to automated replay capture, run `dpl setup` and use the printed `capture.conf` wrapper instead of `manual.conf` in Steam.
