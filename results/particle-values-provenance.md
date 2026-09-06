# Numeric sweep — September 6, 2026

[Report](https://itchyfeetleech.github.io/deadlock-perf-lab/particle-values.html) · [CSV](particle-values-averages.csv) · [Full per-run metrics and hashes](particle-values-data.json) · [PNG](particle-values-summary.png) · [SVG](particle-values-summary.svg)

Session `20260906T035918Z-34a33c` completed all 99 planned captures. All capture hashes, profile hashes, context keys, schedule indices and repeats were checked. Average FPS, 1% low, 0.1% low and P99 frame time were recomputed from each raw capture and matched the saved metrics. All 99 captures are included exactly once. Elapsed time: 60.9 minutes.

Context SHA-256: `c23d36e10d5552e641942e92ff4be72b23619fc0c467125170e813f48083c307`. Plan SHA-256: `e44852dfccde4325c64cc12ce9737ce28081bf4e2888bb70945a90ce5d08c591`. Game build: `24882156`.

Each of 32 variants changes one CVAR and has three captures. Three baseline captures occur at indices 1, 50 and 99. Means weight captures equally. FPS difference is 100 × (variant mean / baseline mean − 1). CV is sample standard deviation / mean × 100. P99 is shown in milliseconds; lower is better. The baseline is the original installed configuration; default values for hidden CVARs are not live-verified. No old-session captures are mixed into these results.

The run deliberately uses one baseline per round. The native report's paired/bracketed verdict is not applicable to this schedule; this publication uses descriptive means. Three repeats do not establish significance. All 96 treatment captures lack individual CVAR readback, and all 99 flag camera/progression review. The public JSON and CSV retain those quality notes. FPS does not isolate CPU time or establish acceptable visual quality.

Reproduce with `PYTHONPATH=src python scripts/publish_value_sweep.py SESSION`, with matplotlib installed. The generator validates the source and writes this report, the webpage, data exports and both plot formats.
