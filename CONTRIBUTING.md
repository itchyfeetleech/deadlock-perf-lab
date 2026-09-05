# Contributing

Useful contributions include reproducible failure reports, capture-format fixtures, recovery tests and clearly labelled community experiments. Avoid universal FPS claims based on one machine or one run.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -v
ruff check src tests
python -m build
dpl --workspace /tmp/dpl-demo demo --open
```

The automated suite never needs a game, desktop session or Steam account. It uses temporary workspaces and fake game/console fixtures for the live orchestration paths. Real integration checks must use a local replay and document the installed game/tool versions.

## Pull requests

Explain the user-visible problem, resulting behavior and relevant checks. Preserve the capture contract: never fabricate data after a live failure, silently remove long stalls, mix benchmark conditions or count frame samples as independent repeated trials. File-changing paths need failure and restoration tests. Keep runtime dependencies minimal and avoid network access or uploads in the CLI.

Add profiles as explicit experimental hypotheses, with source, snapshot date, license, tradeoffs and no claimed benefit without repeatable evidence. Copying someone else's config requires retaining its applicable license and attribution. Do not commit private logs, game binaries, replay files, account identifiers or local machine paths.

Contributions are made under this project's GPL-3.0-only license. By submitting a contribution, you represent that you can provide it under that license.
