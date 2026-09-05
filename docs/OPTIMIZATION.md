# A practical optimization workflow

Treat every change as a hypothesis about a specific machine, build and scene. This suite helps test those hypotheses; the bundled profiles are not universal recommendations or promises of increased FPS.

## Establish a useful control

Record the current game build, hardware, driver/Mesa, Proton, resolution, display mode, graphics settings, upscaling, VSync/VRR, caps and overlays. Keep the same replay, tick, camera and sample length. Warm caches, close unrelated heavy workloads and use repeat rounds. Record changes outside the game's files manually.

If baseline variation or thermal drift is large, stabilize the experiment before expanding the matrix. Use a representative combat scene; menu FPS is a poor proxy for a live match. Keep visual-quality observations alongside performance results.

## What to test

| Area | Treatment | Workflow | Evaluate |
|---|---|---|---|
| Frame pacing | Uncapped vs a chosen FPS cap | Built-in `fps-unlock`, `cap-144`, `cap-240`, or custom cvar | Slow frames, budget misses, power; lower average under a cap is expected |
| Renderer | Current path vs Vulkan / DX11 under Proton | Built-in renderer profiles; verify the selected API | Average and tail frame times after warming both paths |
| Graphics load | Shadows, lighting, AO, particles, textures | Manual profile, one setting at a time | FPS, stalls, GPU load, memory, acceptable visual quality |
| Resolution / scaling | Output resolution and render scale | Manual profile; record each explicitly | Frame times and clarity; do not hide quality differences |
| Upscaling / generated frames | Each supported mode at fixed output settings | Manual profile; separate experiments for different presentation semantics | Clearly label real/rendered vs generated output; capture does not measure latency |
| Community configs | Complete GameInfo snapshot vs your control | Inspect diff, then `--experimental` | Multi-variable result, broken/ignored cvars, camera progression and visibility |
| One cvar | A specific suspected cost | Custom `--autoexec`; readback checked | Whether the setting took effect and has a repeatable practical effect |
| Proton / Mesa / driver | One recorded version or override | Manual experiments | Separate cache warm-up; do not mix versions within one condition set |
| Power / thermal behavior | A deliberate user-managed power policy | Manual experiments | Baseline drift, clocks, temperature and available power sensors |
| Background work / overlays | One process or overlay enabled vs disabled | Manual experiments | Repeatable effect; keep MangoHud constant as instrumentation |
| Asset/shader behavior | Warm vs cold-cache scene | Separate explicitly labelled experiments | Loading/streaming and large stalls; do not call a cold/warm mix a config win |

Many combinations require manual treatment because a game update can rename a setting or change how it is stored. The application does not blindly apply kernel tweaks, install drivers, disable services or delete shader caches.

## Custom cvars and configs

```bash
printf 'fps_max 165\n' > cap165.cfg
dpl profile add cap-165 --autoexec cap165.cfg --description '165 FPS game cap'
dpl profile show cap-165
dpl plan --cases cap-165 --rounds 5
```

Custom cvar files allow assignments and comments. Commands that execute other configs, bind keys, connect to servers or alter the scenario are rejected. Readback checks can catch ignored or rejected variables but do not prove a rendering effect. The original source file is copied into the profile, then frozen again in the plan; later edits do not silently change old experiments.

For a whole-file community comparison:

```bash
dpl profile show community-sqooky --diff
dpl plan --cases community-sqooky --rounds 5 --experimental
```

The four bundled community files are historical snapshots dated 2026-09-04, with attribution and hashes. They change many variables, can be incompatible with a newer game, and can include large quality reductions. Compare your current installation to a reviewed snapshot, then isolate individual changes in follow-up trials. The tool does not fetch or update profiles over the network at runtime.

## What FPS cannot decide

Network rates, interpolation and packet queues concern different workloads and tradeoffs. This suite does not call them FPS optimizations or measure ping/hit registration. It does not measure end-to-end input latency. A high reported frame rate can coexist with poor pacing, visual regressions, a frozen replay or an unintended camera. Verify scene progression and use the metrics for the question they actually answer.
