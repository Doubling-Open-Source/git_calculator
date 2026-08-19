# Changelog

## 2.0.0

Breaking: Python imports use `git_calculator` instead of `src` (for example `from git_calculator import git_ir` instead of `from src import git_ir`). Install with `pip install git-calculator` or `pip install -e ".[dev]"`; `PYTHONPATH=$(pwd)` is no longer required. The CLI is `git-calculator`.
