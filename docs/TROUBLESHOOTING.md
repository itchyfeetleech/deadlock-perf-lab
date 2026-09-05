# Troubleshooting

| Symptom | Action |
|---|---|
| `dpl` not found | Activate the venv or add pipx's application directory to PATH. `python -m deadlock_perf_lab` is an equivalent entry point. |
| Game install not discovered | Set `install` in workspace `lab.json`; it should contain `game/citadel/gameinfo.gi`. Native Steam is the supported launcher. |
| No game within 180 seconds | Sign into Steam, launch Deadlock once normally, finish updates and shader processing, close it, then retry with a new plan. See the run's `steam.log` and Steam's own logs. |
| No MangoHud file | Use the per-game wrapper printed by `dpl setup`; inherited variables on an already-running Steam client are insufficient. Confirm MangoHud works in your Proton game. |
| Old 100 ms / 10 Hz logs | Import/inspect with `--interval-ms 100`; never relabel them `0`. True 1%/0.1% lows and directional verdicts are unavailable. |
| Missing measurement window | Check logging duration and replay length. The parser rejects partial windows instead of treating them as the full test. |
| No VConsole / missing seek confirmation | Game protocol or console output may have changed. Inspect `vconsole.log`; test a local replay using `-dev -vconsole -insecure`. Never expose port 29000 beyond localhost. |
| Replay appears frozen or camera changed | Reject or leave the run unreviewed; choose a valid tick and live target. Do not approve it based only on an FPS number. |
| Cvar readback differs | The current build may reject, rename or protect it. The result stays blocked. Create a compatible treatment instead of waiving the check. |
| Baseline drift or variation | Stabilize thermal state, shader caches, scene and background load, then start a new session. |
| Planned file / system fingerprint changed | Make a new plan. This is an intentional comparison boundary. |
| Experiment already started | Partial sessions remain inspectable. This release starts a new session instead of resuming a partly changed experiment. |
| Workspace path rejected | Avoid commas, equals signs and newlines: MangoHud uses them as config syntax. Ordinary spaces are supported. |

## Recover after interruption

Ctrl+C and SIGTERM request cleanup. SIGKILL, host shutdown and power loss cannot run a handler, so file operations use a durable journal. The backup and original checksum are persisted before each write. A per-install lock prevents simultaneous lab instances, including separate workspaces; a pending journal must be recovered before a new suite.

Close Deadlock, then:

```bash
dpl --workspace /path/to/workspace recover
dpl --workspace /path/to/workspace doctor
```

An existing game is never stopped by the recovery command. Restoration preserves original contents, file mode and absence of files that did not exist before the run. Symlinks are refused. Corrupt/missing backups fail loudly.

If someone edited a file during the benchmark, automatic restoration stops to avoid overwriting that edit. Inspect the current file and journal. To deliberately keep a conflict copy and restore the verified original:

```bash
dpl recover --force
```

Conflict copies live beside the run's backup, under `conflicts/`. Keep the workspace until restoration is verified. Do not delete lock files to bypass another running experiment; the operating system releases the lock when its owner exits.

## Reporting a bug

Include version (`dpl --version`), Linux/Steam/Proton/MangoHud versions, the command, status, reproduction steps and a redacted error excerpt. Use the issue template. Share a report ZIP if useful. Do not upload an entire workspace: raw logs and backups can contain local paths, account identifiers, user configs or other private data.
