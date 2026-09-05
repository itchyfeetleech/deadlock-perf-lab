# Architecture

`dpl` is a Python package using only the standard library at runtime. Live capture uses native Steam, VConsole and MangoHud; manual imports and the demo feed the same analysis and report pipeline.

| Module | Responsibility |
|---|---|
| `cli.py` | Arguments, terminal menu and command dispatch |
| `workspace.py` | Workspace configuration, capture setup and session lookup |
| `profiles.py`, `sweep.py` | Profile validation, bundled snapshots and one-cvar GameInfo variants |
| `planning.py` | Presets, frozen profiles, randomized schedules and plan verification |
| `system.py` | Steam discovery, system/game fingerprints, process identity and install lock paths |
| `runner.py`, `vconsole.py` | Game lifecycle, replay control and capture orchestration |
| `transaction.py`, `storage.py` | Atomic writes, backups, recovery journals and locks |
| `capture.py`, `metrics.py` | MangoHud parsing, window validation, metrics and binned frame-time traces |
| `imports.py` | Ordered manual captures and operator review records |
| `analysis.py` | Evidence checks, round comparisons, timing summaries and shortlists |
| `report.py`, `assets/report.html` | Offline HTML, Markdown, JSON, CSV and ZIP exports |

Capture and import code do not depend on report rendering. Plans own the experiment's conditions and schedule; analysis checks results against that plan before comparison. Metric definitions and verdict rules live in the [methodology](METHODOLOGY.md).

## Saved data (schema 1)

```text
.lab/
  lab.json                         # user-edited conditions and scenario
  capture.conf / manual.conf        # MangoHud configuration
  profiles/<id>.json                # custom profile snapshots
  imports/                         # manually captured logs
  sessions/<UTC>-<random>/
    plan.json                      # frozen plan with SHA-256
    status.json / events.log
    runs/001-baseline/
      result.json / window.json
      capture/*.csv                # automated capture
      capture.csv                  # imported or demo capture
      steam.log / vconsole.log
      transaction.json / backup/
      review.json                  # operator verification
      timings.json                 # live run phase durations
    report/index.html / summary.* / runs.csv
```

Plans cannot be edited or resumed after starting. Create a new plan when conditions change; historical sessions remain readable. Unsupported schemas are rejected. Old aggregate `results.csv` files lack the capture-window evidence needed for import.

## Recovery and export boundaries

A write-ahead journal records backups before changing files. An install-wide `flock` and pending-journal pointer in the user's cache protect concurrent workspaces. PID start times are checked before signalling the game. See [recovery instructions](TROUBLESHOOTING.md#recover-after-interruption).

Reports embed their data and browser assets in one HTML file. Text is escaped, and the ZIP exporter includes only the four report files. Labels and notes remain user-authored content; see [security and data handling](../SECURITY.md).
