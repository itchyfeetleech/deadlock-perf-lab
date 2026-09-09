<div align="center">

# DPL - Deadlock Performance Lab

**Deadlock benchmarking for Linux.**

[![CI](https://github.com/itchyfeetleech/deadlock-perf-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/itchyfeetleech/deadlock-perf-lab/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-d0df9c)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-Linux-d0df9c)](docs/QUICKSTART.md)
[![GPL v3](https://img.shields.io/badge/license-GPLv3-d0df9c)](LICENSE)

[Community benchmark results](https://itchyfeetleech.github.io/deadlock-perf-lab/) · [Numeric value sweep](https://itchyfeetleech.github.io/deadlock-perf-lab/particle-values.html) · [Get started](docs/QUICKSTART.md) · [Testing configs](docs/OPTIMIZATION.md) · [Methodology](docs/METHODOLOGY.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

</div>

Compare Deadlock settings on Linux using repeated replay captures and MangoHud frame-time logs. The tool runs configurations against your current setup and reports FPS, slow frames and uncertainty in the difference.

**Early preview (0.2).** Replay automation depends on the installed game build. You must check camera position and playback before the tool will mark a result as improved or regressed.

## Install and try

Requires Linux and Python 3.11+. Install with [pipx](https://pipx.pypa.io/stable/installation/):

```bash
pipx install 'git+https://github.com/itchyfeetleech/deadlock-perf-lab.git@v0.2.0'
dpl demo --open
```

The demo opens a report with synthetic data; no game installation is needed. Run `dpl` for the terminal menu or `dpl --help` for commands.

<details>
<summary>Example report — synthetic data</summary>

![Benchmark report with configuration comparisons and frame-time traces; all values are synthetic](docs/images/report-desktop.png)

</details>

## Benchmark your setup

Live captures need native Steam, Deadlock, Proton, MangoHud and a local replay. Follow the [first experiment guide](docs/QUICKSTART.md) to configure capture, select a replay scene and run a comparison.

Each round tests your current setup before and after the selected configurations. Changes are temporary and restored after the run. If a power loss or hard kill interrupts restoration, close Deadlock and run `dpl recover`.

Results compare settings on your machine and scene. An improvement verdict needs at least five complete rounds and cleared measurement checks. The tool does not permanently apply configurations.

- [Test graphics and other settings manually](docs/MANUAL_EXPERIMENTS.md)
- [Test custom configs and screen a large set](docs/OPTIMIZATION.md)
- [Understand the measurements](docs/METHODOLOGY.md)
- [Troubleshoot setup and captures](docs/TROUBLESHOOTING.md)

Reports open offline in a browser. Use `dpl export --output report.zip` to share one; review your labels and notes first, as they are included.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and reporting bugs.

[GPL-3.0-only](LICENSE). Bundled config credits and licenses are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Independent community project, unaffiliated with Valve.
