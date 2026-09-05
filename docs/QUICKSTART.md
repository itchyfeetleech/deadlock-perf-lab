# Your first experiment

## Requirements

Linux, Python 3.11+, native Steam signed into an account with Deadlock access, a working Proton installation and MangoHud. Install MangoHud using your distribution's packages; some setups also need its 32-bit package. Flatpak Steam, remote streaming and Windows automation are outside this release's support scope. The offline demo and analysis need only Python.

Use the release wheel or the pinned GitHub install command in the README. No background service, telemetry account or administrator access is required by this application.

## 1. Create a workspace

```bash
dpl init --replay replays/my-match.dem
```

Steam libraries are discovered from standard locations and `libraryfolders.vdf`. If needed:

```bash
dpl init --install '/mnt/games/steamapps/common/Deadlock' --replay replays/my-match.dem
```

The default workspace is `.lab` in the current directory. Use `dpl --workspace /path/to/experiments COMMAND` consistently to keep it elsewhere. Workspaces contain private local data and should not be committed.

## 2. Freeze the scene and conditions

Download a replay through the game and put its `.dem` under the game's `game/citadel/replays/` directory. Replays are not distributed by this project. Open `.lab/lab.json` in your editor and set:

| Field | Purpose |
|---|---|
| `scenario.replay` | Absolute or `game/citadel`-relative path, inside that directory |
| `scenario.tick` | Start of a representative section, with enough playback left |
| `scenario.player` | Explicit spectator target accepted by the current game build |
| `scenario.warmup_s` | Playback warm-up before seeking back; default 45 s |
| `scenario.settle_s` | Brief settle after selecting camera; default 5 s |
| `scenario.sample_s` | Capture duration; default 30 s |
| `scenario.budget_fps` | Target FPS used for frame-budget misses; default 144 |
| `conditions` | Resolution, graphics preset, Proton version, display mode and other controlled settings |

Prefer a representative fight over a menu or empty scene. Keep the selected target alive during the whole window. Warm each renderer/Proton path before drawing conclusions. For an exploratory bot stress scene, set `scenario.mode` to `bots`; the default map is `dl_midtown`. Random bot behavior prevents directional verdicts in this release.

A baseline preserves whatever GameInfo and autoexec you already use. Restore the stock game yourself first if that is your intended control. Record your existing Steam launch flags in `conditions.notes`; the suite cannot infer every Steam or driver override.

## 3. Wire up per-game capture

```bash
dpl doctor
dpl setup
```

Paste the printed command into Deadlock → Steam Properties → General → Launch Options. It has this form:

```text
env -u MANGOHUD_CONFIG MANGOHUD=1 MANGOHUD_CONFIGFILE='/absolute/workspace/capture.conf' %command%
```

Keep unrelated launch arguments after `%command%`. Existing wrappers such as GameMode/gamescope need to be composed deliberately; record the final launch options in your conditions. Do not duplicate `%command%`.

This setting makes the game read the workspace's capture configuration at launch, even when Steam is already running. Passing MangoHud variables only to `steam -applaunch` does not update an existing Steam client's environment. Outside a benchmark the generated configuration leaves logging off. Remove the wrapper from Steam if you delete or move the workspace.

## 4. Inspect and plan

```bash
dpl profile show fps-unlock
dpl plan --cases fps-unlock --rounds 5
```

The plan records exact profile contents, source hashes, the replay hash, current build, baseline file hashes, available system identity, stated conditions and seed. Treat the plan as immutable. To change it, make a new one.

Each round is baseline → shuffled treatments → baseline. Five rounds of one treatment means 15 game launches. Allow time for loading and seeking in addition to the printed warm-up/capture timing. Start with a baseline-only smoke test if needed:

```bash
dpl plan --cases baseline --rounds 1
dpl run --live
```

## 5. Run and verify

Close Deadlock, then run:

```bash
dpl run --live
```

The suite launches only local replay/bot scenarios and includes `-insecure`. It writes `autoexec_dpl.cfg`, optionally swaps GameInfo for an explicitly selected experimental profile, sets a unique per-run MangoHud output directory, then restores originals. Config changes are temporary.

Keep the benchmark visible, do not interact with the camera during sampling, and avoid unrelated GPU/CPU work. Use a terminal that stays open. Ctrl+C or SIGTERM requests cancellation and restoration; an uncatchable kill or power loss requires `dpl recover` after closing the game.

Inspect `runs/<id>/vconsole.log` for applied settings and watch the game view for camera and replay progression. `demo_info` describes the replay file; it does not establish the current playback position. A successful socket send does not establish that a cvar took effect. Simple cvar treatments have readback checks. Whole-file and renderer effects still need operator review.

```bash
dpl review --run 001-baseline --note 'Watched this capture: the selected player POV stayed fixed and replay time advanced throughout the window.'
```

Review only captures you actually checked, using their exact IDs. The command records the confirmation and note; it cannot waive malformed data, interval logging, missing conditions or failed cvar readback. Every baseline and treatment relevant to a comparison needs its applicable checks cleared.

## 6. Interpret and share

```bash
dpl report --open
dpl compare
dpl export --output report.zip
```

Look at baseline variation and drift first, then average FPS, slow frames and practical tradeoffs. A deliberate cap can reduce average FPS while improving pacing. Rerun promising results in a fresh session instead of choosing the largest noisy number from a large sweep.
