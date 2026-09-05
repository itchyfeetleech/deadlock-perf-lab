# Releasing

1. Update the version in `pyproject.toml` and `src/deadlock_perf_lab/__init__.py`, the changelog and pinned installation examples.
2. Run `python -m unittest discover -v`, `ruff check src tests` and `python -m build` in the development venv.
3. Install the built wheel into a fresh venv outside the checkout. Run `dpl --version`, `dpl profiles` and a complete `dpl demo`. Confirm package assets and licenses are present.
4. Verify the report's comparison table, run selector, exports, narrow-screen layout and absence of script errors. Synthetic previews must retain their watermark.
5. Record live smoke-test scope and limitations separately. Never label simulated backend tests as live measurements. Check `dpl doctor` and restoration after any failed live attempt.
6. Inspect the exact staged manifest. Exclude `.lab`, experiments, private history, logs, replay binaries, backups, credentials and machine-specific notes. Review bundled third-party hashes and license notices.
7. Push the commit and require the CI workflow to pass, including supported Python versions and the installed-wheel smoke test. Tag the matching commit and attach wheel, sdist and checksums to the GitHub release.

The `0.1.0` tag is a community preview/pre-release. Do not claim Windows/Flatpak automation, universal configuration gains or automatic camera fidelity verification. Runtime schema migration, cross-session meta-analysis and automatic visual validation are possible future work; they are not shipped features.
