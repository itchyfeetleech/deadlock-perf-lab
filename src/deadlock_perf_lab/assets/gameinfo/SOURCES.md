# Community snapshot provenance

Source: [Sqooky/OptimizationLock](https://github.com/Sqooky/OptimizationLock).
The existing research workspace fetched these files on 2026-09-04. They are redistributed unchanged.
Upstream main observed during release preparation: `3167965cae607c24fd04c1df021178f1536c58a3`.
The SHA-256 below identifies the exact bundled bytes; this is not a claim that every file is current.

License: GPL-3.0-only; the accompanying LICENSE reproduces the upstream license text.
Credit belongs to Sqooky, Boot, Kaizuchaneru and the contributors acknowledged by OptimizationLock.

| Bundled file | Upstream path | Bytes | SHA-256 |
|---|---|---:|---|
| `sqooky-default.gi` | `Sqooky's .gi/gameinfo.gi` | 86824 | `946a430112370dafcbeb8c2b72374bb68c1fe7e0e7d2e5c7238a1bd2002a6067` |
| `sqooky-maxfps-test.gi` | `test_cfg/gameinfo.gi` | 88208 | `362c7c577c37f821cf9f484f4505c7a21afecc014e3064e77798ede620189d55` |
| `boot-maxfps.gi` | `boot's maxium fps config/gameinfo.gi` | 71537 | `6dbc82150afe2ec409646025b2437b093aab18d852a7329b80aded2ffb7cf0e5` |
| `kaizu-minspec.gi` | `kaizuchanerus minimum spec/gameinfo.gi` | 52281 | `16e9e739b90941543f2fabeea8161fd15327df5f16d812377fbd2bf4e75a98a4` |

These are whole-file experimental replacements, not single-cvar patches.
Boot is described upstream as unmaintained. The test and minimum-spec variants have substantial compatibility/visual tradeoffs.
The package never auto-downloads, auto-updates or persistently installs these files.
Review the actual diff against your current installation before use. New game builds can invalidate assumptions.
