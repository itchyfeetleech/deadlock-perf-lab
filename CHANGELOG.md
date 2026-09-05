# Changelog

## Unreleased

- Removed the report header badge, baseline-history panel, iteration-time panel and Print/PDF button.
- Replaced the sort dropdown with reversible sorting on every configuration column.
- Consolidated configuration guides, release instructions and validation notes; shortened the README and CLI guide.
- Separated workspace setup, plan creation, capture processing and report rendering. Commands and saved-data formats are unchanged.

## 0.2.0 — 2026-09-06

- Rebuilt results around a searchable, sortable configuration table with average FPS, 1% low, P99 time and paired effects.
- Added linked capture overlays, selected-effect intervals, sensor tables, baseline history and comparison CSV export.
- Added the 5-second scouting preset and per-phase iteration timings. Reduced camera-command guard overhead in new plans.
- Preserved old plan behavior, evidence checks, recovery and offline report compatibility.

Validation recorded for this release: 51 automated tests; a live baseline → GameInfo → baseline scout completed with restoration verified. Iterations took 27.7, 69.5 and 24.3 seconds; Steam shader processing accounted for 50.5 seconds of the middle launch. The report was inspected with synthetic data and an existing partial sweep, including sorting, capture selection and a 390-pixel layout. Shorter scout captures are not evidence of an equivalent-duration speedup.

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

Validation recorded for this release: 48 automated tests and two three-run live replay sessions on Linux with native Steam, Proton and MangoHud. Capture and restoration completed. A GameInfo sequence had a 34.7-second median iteration with 10-second captures and 5-second warm-up; cold launches varied substantially. These smoke tests do not establish an optimization winner or replace camera/playback review.

Historical aggregate rows from the prototype are not accepted as validated measurements.
