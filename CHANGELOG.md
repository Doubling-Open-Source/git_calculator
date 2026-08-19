# Changelog

## [Unreleased]

## [2.1.0] - 2026-08-19

### Added

- Add `--work-style squash` so squash-merge clones follow the default branch and score change-failure from the commit summary only.

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [PEP 440](https://peps.python.org/pep-0440/).

## [2.0.1] - 2026-08-19

### Fixed

- Add Changesets and Keep a Changelog formatting for GitHub Releases.

## [2.0.0] - 2026-08-19

### Changed

- Breaking: Python imports use `git_calculator` instead of `src` (for example `from git_calculator import git_ir` instead of `from src import git_ir`). Install with `pip install git-calculator` or `pip install -e ".[dev]"`; `PYTHONPATH=$(pwd)` is no longer required. The CLI is `git-calculator`.
