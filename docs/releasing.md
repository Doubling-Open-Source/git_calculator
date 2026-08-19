# Releasing

This repo versions with [changesets](https://github.com/changesets/changesets) (`patch` / `minor` / `major`). How to add a changeset: `docs/changesets.md`.

## Publish

```
scripts/gh-release.sh --dry-run
scripts/gh-release.sh
```

If there are pending `.changeset/*.md` files, that applies them (highest bump wins), rewrites `CHANGELOG.md` to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), copies the PEP 440 version into `pyproject.toml`, commits `chore: release vX.Y.Z`, and publishes.

If there are **no** pending changesets, it publishes the version already in `pyproject.toml`. Use that to finish a run that stopped after the bump (for example `python -m build` failed) or after a local `chore: release` commit.

`--current` is the same publish path but refuses to run when changesets are still pending.

## Idempotent tags

If `vX.Y.Z` already exists but the GitHub Release does **not**, the script moves that tag to `HEAD` (`git tag -f` and `git push --force` of the tag only) and creates the release. If the GitHub Release already exists, it exits 0 and does nothing.

Do not use this to rewrite a release people already downloaded.

## Tooling

Needs authenticated `gh`, Node.js (`npm install` for `node_modules/.bin/changeset`), and a repo-local `.venv` (created automatically) with the `build` package. Homebrew Python cannot `pip install` into the system interpreter (PEP 668).
