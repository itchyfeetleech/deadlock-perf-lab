# Changelog

## Unreleased

- Removed the report header badge, baseline-history panel, iteration-time panel and Print/PDF button.
- Replaced the sort dropdown with reversible sorting on every configuration column.


## 0.2.0 — 2026-09-06

- Rebuilt results around a searchable, sortable configuration table with average FPS, 1% low, P99 time and paired effects.
- Added linked capture overlays, selected-effect intervals, sensor tables, baseline history and comparison CSV export.
- Added the 5-second scouting preset and per-phase iteration timings. Reduced camera-command guard overhead in new plans.
- Documented comparable profiling tools and Steam shader-processing startup delays.
- Preserved old plan behavior, evidence checks, recovery and offline report compatibility.


## 0.1.0 — 2026-09-05

First packaged Linux community preview.

- Replaced the script collection with an installable `dpl` application and guided terminal menu.
- Added frozen, randomized experiment plans with baseline-bracketed repeat rounds.
- Added event-driven replay readiness, screen/confirm presets, profile selectors, one-cvar matrix generation, timing summaries and provisional shortlists.
- Added per-frame MangoHud parsing with explicit capture windows, long-stall retention and capture-integrity checks.
- Added replay/bot automation, readback evidence, install-wide serialization and crash recovery journals.
- Added custom profiles, attributed community snapshots and manual-capture experiments.
- Added round-level confidence intervals, baseline stability checks and operator-verification gates.
- Added offline interactive reports, CSV/JSON/Markdown and private-by-default report ZIP exports.
- Added tests, Linux CI, wheel/sdist builds, installation, methodology, optimization and contributor guides.

Historical aggregate rows from the prototype are not accepted as validated measurements. The prior full-startup parser and synthetic fallback behavior are not part of this package.
