# Measurement and inference

## Capture contract

Live capture uses MangoHud `log_interval=0`, one row per rendered frame. MangoHud's `elapsed` field is nanoseconds since logger start ([source](https://github.com/flightlessmango/MangoHud/blob/master/src/logging.cpp)). The CSV header is detected dynamically, including versioned logs and variable telemetry columns.

The runner waits for a fresh game process, a run-specific Deadlock CSV and the engine's completed demo-signon message. After replay warm-up it seeks back to the requested tick, pauses to establish the camera, records the latest complete logger timestamp and resumes. The analysis window is `[start_elapsed_s, start_elapsed_s + sample_s)`. It stops the game to finalize the file before hashing and parsing it. Startup, loading and warm-up are outside that interval. There is a small command/CSV sampling alignment error; this is not tick-exact frame capture or a deterministic engine timedemo.

A positive finite frame time is retained regardless of size. Nonpositive, NaN, infinite and malformed rows are counted and disclosed; automated verdicts remain blocked when they occur. Missing logs, insufficient samples, backwards timestamps, mismatched per-frame coverage and incomplete windows fail the capture. No real-run fallback produces synthetic FPS or CPU data.

Per-frame assertions are checked by comparing elapsed coverage with summed frame times (80–120% tolerance). This catches ordinary interval-logged captures mislabelled as per-frame, but is a plausibility check rather than proof of complete instrumentation. A known interval must still be declared on import.

## Metrics

All frame-time values are milliseconds. Quantiles linearly interpolate the sorted data at `(N - 1) × percentile`.

| Metric | Definition |
|---|---|
| Average FPS | `1000 / mean(frame_ms)` |
| 1% low FPS | `1000 / mean(slowest ceil(0.01 × N) frame_ms)` |
| 0.1% low FPS | Same calculation with `0.001`; shown only with at least 1,000 per-frame samples |
| Inverse P99 FPS | `1000 / P99(frame_ms)`; distinct from the slow-tail mean |
| P95 / P99 | Frame-time percentiles; smaller is better |
| Maximum frame | Largest positive finite frame time, with no clipping |
| Budget misses | Percentage of samples longer than `1000 / budget_fps` |
| Stalls | Counts above 50 ms and above 100 ms; descriptive thresholds, not a stutter diagnosis |
| Telemetry | Available MangoHud CPU/GPU load, temperature, clocks, memory and power summaries |

Telemetry is sampled by MangoHud on its own update cadence and may repeat between frames. CPU load here is MangoHud system CPU load, not a process CPU profile. Zero telemetry can mean unsupported sensors; do not interpret it as proof of idle hardware. The report's plots group frame times into min/mean/max bins for display; statistics always use the full selected window.

Interval captures retain sampled FPS estimates and sample percentiles but suppress true 1%/0.1% lows and directional performance verdicts. They must not be mixed with per-frame captures.

## Experiment units

The independent unit is a complete **round**, not an individual frame. Each round contains an opening baseline, each requested treatment once in a seeded shuffled order, and a closing baseline. For treatment `T` in a round:

```text
control = mean(opening baseline FPS, closing baseline FPS)
round change = 100 × (T FPS / control - 1)
```

The reported effect is the mean round change. A deterministic percentile bootstrap resamples complete round changes 4,000 times to estimate a 95% interval. This avoids pretending that thousands of correlated frames are thousands of independent experiments, but assumes rounds reasonably represent the conditions of interest. The two baseline controls are averaged; there is no claimed time-interpolated drift correction.

At least five complete paired rounds are required for a directional verdict. Baseline CV and absolute opening-to-closing drift must both be no greater than the practical threshold (default 3%). All planned treatment rounds must be complete, capture context and profile fingerprints must match, raw hashes must verify and quality checks must be cleared. A CI wholly above +threshold yields “improved”; wholly below -threshold yields “regressed”; wholly inside the threshold band yields “within threshold.” Otherwise the result is inconclusive. Synthetic data always says “demo.”

The verdict describes **average FPS**, not overall game quality. Inspect lows, stalls, power, stability and visibility separately. FPS-cap profiles need particular care: lower average FPS can be intentional.

## Evidence limits

These are exploratory intervals, uncorrected for multiple comparisons. A broad search can produce a lucky winner; confirm the selected change in a fresh experiment. Thermal equilibrium, shader caches, background load, renderer/Proton differences and game updates can all invalidate a comparison. Hardware identification does not capture every driver control-panel or Steam option; record those in the conditions.

Replay and camera state still need operator verification because Source 2 remote-console output changes between builds. The tool saves raw output and refuses directional conclusions until those checks are reviewed. Random bot matches are explicitly exploratory. A replay does not reproduce every CPU/network workload of a live match. Render timing is not an input-to-photon latency measurement, network benchmark or guarantee of competitive visibility.

Legacy data from the original scripts has insufficient sample-window provenance and sometimes 100 ms logging. Use `dpl audit-legacy old/results.csv` and `dpl inspect raw.csv --interval-ms 100` to inspect it; aggregate legacy rows are not accepted as validated new trials.
