# Releasing

Version bumps come from [changesets](https://github.com/changesets/changesets): `patch`, `minor`, or `major`. Do not hand-edit `pyproject.toml` / `package.json` versions for a release.

## 1. Record the change

On the feature branch:

```
npx changeset
```

Pick the bump, write the summary, and commit the new file under `.changeset/`.

## 2. Cut the GitHub Release

From a clean `main` that includes those changeset files (`gh` authenticated, Node.js + Python `build` extra installed):

```
scripts/gh-release.sh --dry-run
scripts/gh-release.sh
```

The script applies pending changesets (highest bump wins), syncs `pyproject.toml`, commits `chore: release vX.Y.Z`, tags `vX.Y.Z`, pushes, and creates the GitHub Release with sdist/wheel assets. Release notes are the new `CHANGELOG.md` section for that version.
