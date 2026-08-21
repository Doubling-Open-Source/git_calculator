# AGENTS.md

## Cursor Cloud specific instructions

`git-calculator` is a Python 3.11+ CLI that computes DORA-style metrics from a local Git
repository (cycle time, change failure rate, throughput, active developers) and renders CSVs +
matplotlib charts. There is no server/UI; the product is the CLI and its Python API. Node is only
used for docs tooling and changesets.

The startup update script already provisions a Python virtualenv at `./venv` (dev extras) and runs
`npm ci`. Activate the venv before working: `source venv/bin/activate`.

### Run / test / lint / build

- Run the app (see `README.md` for full usage):
  - `git-calculator single /path/to/repo` — analyze one repo. Output CSVs/PNGs are written to a
    `metrics/` directory in the current working directory (the `--output` value is logged but charts
    land in `metrics/`).
  - `git-calculator config --create-sample` then `git-calculator multi --config repo_config.json`.
- Test: `pytest tests/ -v`. Set `git config --global user.{name,email}` first — many tests build
  toy Git repos and fail without a Git identity (CI sets these).
- Lint/format: via pre-commit (`pre-commit run --all-files`). CI does NOT gate on lint (only
  `pytest` and `npm run docs:check`).
- Docs check (CI-gated): `npm run docs:check`.

### Non-obvious gotchas

- Run the test suite with `CI=true pytest tests/` to match CI. The 4 chart-snapshot tests in
  `tests/test_chart_snapshots.py` do pixel comparisons and are intentionally skipped when
  `CI=true`; without that flag they FAIL on this environment due to OS/matplotlib/font rendering
  differences (not a real regression). The full suite takes ~10 min; the first chart test is slow
  because matplotlib builds its font cache.
- `pip install ruff` gets a newer ruff whose default rule selection is much larger than the
  project's pinned `ruff 0.15.1` (see `.pre-commit-config.yaml`), so a bare `ruff check .` reports
  hundreds of spurious findings. Lint through pre-commit (pinned ruff) instead of a globally
  installed ruff.
- The `oxipng` pre-commit hook compiles from source and needs Cargo >= 1.85 (`edition2024`); the
  system Cargo is older, so that single hook fails to install. The code-lint hooks (`ruff`,
  `ruff-format`, `codespell`) work fine — run them individually if `pre-commit run --all-files`
  aborts on `oxipng`.
- `node_modules/` is not covered by `.gitignore`; do not stage it.
