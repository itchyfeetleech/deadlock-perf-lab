# Results presentation: references and decisions

Reviewed 6 September 2026. These tools informed the report workflow; their screenshots, code and branding are not bundled.

| Reference | Relevant pattern | Applied in Deadlock Perf Lab |
|---|---|---|
| [CapFrameX features](https://www.capframex.com/features) | Metric sorting, capture comparisons, frame-time overlays, selectable records and run aggregation | A searchable configuration table, selectable metric sorting, linked capture selection and two traces on shared axes |
| [Intel PresentMon](https://game.intel.com/ch/intel-presentmon/) | Performance timing alongside telemetry; multiple series and histograms | Capture timing and available sensor readings are adjacent. MangoHud GPU utilization is not labelled GPU Busy; unsupported metrics remain unavailable |
| [NVIDIA FrameView guide](https://www.nvidia.com/content/dam/en-zz/Solutions/GeForce/technologies/frameview/FrameView_Beta_User_Guide.pdf) | Explicit distinctions between average and percentile timing metrics and their capture points | Average FPS, slowest-frame-mean 1% low and P99 milliseconds have separate labels and definitions. No rendered/displayed latency claims are inferred from MangoHud |
| [Phoronix Test Suite features](https://www.phoronix-test-suite.com/index.php?k=features) | Repeated tests, variability checks and additional trials when variation is excessive | Baseline variation, confidence intervals and verification reasons remain available. Screening rankings require a separate confirmation experiment |

## Reading the report

1. Check recorded/planned capture counts and the review notice. A positive value is not automatically a verified improvement.
2. Search configurations or click a column header to sort in either direction. The baseline remains at the top. Rows show average FPS, 1% low, P99 frame time, paired FPS change, complete paired rounds and verdict.
3. Select a configuration. Its panel shows the paired effect, 95% interval when available, practical threshold and reasons a verdict is withheld. FPS bars use a common zero-based scale.
4. Compare an individual capture with a baseline from the same round. Both traces share axes. Time zero is the start of each capture, not proof that scenes align. Dashed peaks retain the largest frame in each display bin.
5. Inspect excluded runs, sensor readings and recorded conditions before sharing. Iteration timings remain available through `dpl timings`.

Configuration metrics are equal-weight means of per-capture metrics, not metrics from concatenated frames. Every required capture must support a tail metric for its aggregate to be displayed. Missing values are shown as a dash. Counts are integers. The JSON and CSV exports retain numerical precision.

The report deliberately avoids an oversized title section, decorative summary scores and automatic bottleneck diagnoses. It remains a single offline HTML file, with a basic comparison table and quality notes available without JavaScript. Long tables scroll within their own area; filtering does not discard any evidence from the export.
