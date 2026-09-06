# Community screen: September 6, 2026

[Interactive results](https://itchyfeetleech.github.io/deadlock-perf-lab/) · [CSV with quality notes](teamfight100-three-repeat.csv)

100 one-CVAR GameInfo variants, three successful captures each and three baseline captures. The first session stopped after 231 captures; a continuation supplied the remaining 72. All 303 successful captures are included once, with no selection based on FPS. The source sessions have identical frozen profile and context hashes. Each published FPS mean was checked against the records, and every raw-capture hash was verified before publication.

Recorded source sessions: `20260905T230142Z-03850b` and `20260906T014321Z-db841b`. Context hash: `c23d36e10d5552e641942e92ff4be72b23619fc0c467125170e813f48083c307`. Matching context means matching recorded conditions; it is not evidence of zero performance drift.

Machine: Ryzen 7 9800X3D, Radeon RX 9070, Linux/Proton, 1280×720 with existing custom low settings. Replay `102565106.dem`, tick 134987, player 1/chase view, 10-second captures after 10 seconds of warm-up and a final seek. Per-run configuration restoration and fresh game processes were used. Raw game files, demo, account data and local workspace paths are not included in this publication.

Means are descriptive, compared against the mean of three baselines. The CSV includes FPS, 1% and 0.1% lows, P99 frame time, individual rounded FPS values, coefficient of variation, and quality notes. The page's positive P99 percentage is the inverse-frame-time improvement, `100 × (baseline P99 / treatment P99 − 1)`; it is not the percentage decrease of P99 milliseconds. Many settings could not be read back; requested values are not proof of engine application. Camera and visual-effect verification remain outstanding. These results do not establish statistical significance or recommend settings for every machine.
