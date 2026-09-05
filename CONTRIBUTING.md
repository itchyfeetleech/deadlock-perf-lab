# Contributing

Bug reports should include the command, steps to reproduce, relevant versions and a short error excerpt. A report ZIP can help; avoid uploading an entire workspace, which may contain account identifiers, local paths and user configs.

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

Tests use temporary workspaces and fake game/console fixtures; they do not need Steam or a game installation. See [architecture](docs/ARCHITECTURE.md) for module responsibilities and the saved-data layout.

## Pull requests

Explain the problem, resulting behavior and relevant checks. Changes to capture or analysis should preserve the [measurement rules](docs/METHODOLOGY.md). File-changing paths need failure and restoration tests. Keep runtime dependencies minimal.

New profiles need a source, snapshot date, license and known tradeoffs. Retain attribution when copying configs, and support performance claims with repeated measurements. Do not commit raw experiments, game binaries or replay files. Contributions use this project's GPL-3.0-only license.

## Releases

1. Update the version in `pyproject.toml` and `src/deadlock_perf_lab/__init__.py`, the changelog and pinned README install command.
2. Run the tests, lint and build commands above. Install the wheel into a fresh venv outside the checkout; check `dpl --version`, `dpl profiles` and `dpl demo`.
3. Check report sorting, capture selection, exports and narrow-screen layout. Keep synthetic previews labelled. Record any live smoke tests and their limits in the changelog separately from automated tests.
4. Inspect the distribution contents for package assets, licenses and accidentally included local data.
5. Push and require CI to pass, then tag the matching commit and attach the wheel, sdist and checksums to a GitHub release. Mark `0.x` releases as previews.
