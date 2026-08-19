# Releasing

This repo versions with [changesets](https://github.com/changesets/changesets) (`patch` / `minor` / `major`). After this tooling lands, you do **not** run `changeset init` again: `.changeset/config.json` and the `git-calculator` entry in `package.json` are the integration.

## Bootstrap (once)

1. Install the CLI (from repo root): `npm install`
2. Publish the version **already** on `main` (`2.0.0` today). There is nothing to bump yet, so do **not** add a changeset:

```
scripts/gh-release.sh --current --dry-run
scripts/gh-release.sh --current
```

That tags `v2.0.0` and creates the GitHub Release from the existing `CHANGELOG.md` / `pyproject.toml` version.

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

That applies pending changesets (highest bump wins), syncs `pyproject.toml`, commits `chore: release vX.Y.Z`, tags, pushes, and attaches sdist/wheel assets.

Needs a clean tree, authenticated `gh`, Node.js, and `pip install -e ".[dev]"` (for `python -m build`).
