# Releasing

This repo versions with [changesets](https://github.com/changesets/changesets) (`patch` / `minor` / `major`). How to add a changeset: `docs/changesets.md`.

## First GitHub Release

`main` is at **2.0.0** in `pyproject.toml` and already has a pending **patch** changeset (Keep a Changelog / Changesets). `--current` refuses to run while any `.changeset/*.md` (other than README) is pending, so do **not** use `--current` for this first publish.

```
npm install
scripts/gh-release.sh --dry-run
scripts/gh-release.sh
```

That applies the pending patch, publishes **2.0.1**, tags `v2.0.1`, and creates the GitHub Release.

`--current` is only for tagging the version already in `pyproject.toml` when there are **no** pending changesets.

## Later releases

On each feature PR that should ship:

```
npx changeset
```

Pick patch, minor, or major, write the summary, commit the new `.changeset/*.md` file.

After those PRs are on `main`:

```
scripts/gh-release.sh --dry-run
scripts/gh-release.sh
```

That applies pending changesets (highest bump wins), rewrites the new `CHANGELOG.md` block to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (`Added` / `Changed` / `Fixed`), copies the PEP 440 version into `pyproject.toml`, commits `chore: release vX.Y.Z`, tags, pushes, and attaches sdist/wheel assets. GitHub Release notes are that version's Keep a Changelog body.

Needs a clean tree, authenticated `gh`, Node.js (`npm install` so `node_modules/.bin/changeset` exists), and `pip install -e ".[dev]"` (for `python -m build`).
