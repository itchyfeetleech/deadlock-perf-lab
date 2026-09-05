# Architecture

The installed `dpl` executable delegates to a stdlib-only Python package. There is no runtime service, remote API or self-updater.

```text
CLI / guided menu
  ├── workspace + profiles → immutable plan
  ├── runner → Linux Steam / VConsole / per-run MangoHud
  │     └── file transaction journal → verified restoration
  ├── manual imports → same capture validation
  └── capture → metrics → round-level analysis → offline report/export
```

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing, menu and public commands |
| `workspace.py`, `profiles.py` | Configuration, discovery integration, validation, copied assets and frozen schedules |
| `system.py` | Read-only Steam library discovery, game/system fingerprints and executable-specific PID identities |
| `runner.py`, `vconsole.py` | Serialized game lifecycle, local engine control, warm-up/reseek and isolated log windows |
| `transaction.py`, `storage.py` | Atomic writes, checksummed backups, write-ahead journals and locks |
| `capture.py`, `metrics.py` | Dynamic MangoHud parsing, coverage checks and explicit metric definitions |
| `planning.py`, `sweep.py` | Screening presets, runtime summaries, provisional shortlists and single-cvar GameInfo matrix generation |
| `imports.py` | Ordered manual captures and hash-bound operator review records |
| `analysis.py` | Context/digest checks, independent round comparisons and uncertainty gates |
| `report.py`, `assets/report.html` | Escaped, self-contained HTML/JSON/Markdown/CSV and allowlisted ZIP exports |

## Workspace data (schema 1)

```text
.lab/
  lab.json                         # user-edited conditions and scenario
  capture.conf / manual.conf        # per-game MangoHud configuration
  profiles/<id>.json                # user treatment snapshots
  imports/                         # user-captured logs
  sessions/<UTC>-<random>/
    plan.json                      # immutable, SHA-256 protected
    status.json / events.log
    runs/001-baseline/
      result.json / window.json
      capture/*.csv                # finalized raw automated capture
      capture.csv                  # imported or demo capture
      steam.log / vconsole.log     # local evidence, excluded from sharing
      transaction.json / backup/
      review.json                  # optional operator verification
    report/index.html / summary.* / runs.csv
```

File journals survive process death. An install-wide `flock` and pending-journal pointer under the user's cache directory protect concurrent workspaces. PID start times are checked before signals so a reused PID is not killed. The runner never uses shell `eval`, shell string commands or broad `pkill` patterns.

The report format is independent of the Python package once generated. Browser assets are inline; charts use native canvas and DOM, labels use `textContent`, JSON escapes `<`, and table content is HTML-escaped. The ZIP exporter has an explicit filename allowlist. Reported source hashes identify evidence without shipping raw logs.

## Compatibility

Schema 1 is intentionally small. Incompatible schemas are rejected rather than guessed. Plans cannot be edited or resumed after starting. Create a new plan for changed conditions; keep historical sessions for inspection. No conversion of old aggregate `results.csv` rows into validated trials is provided because the missing capture-window provenance cannot be recreated reliably.
