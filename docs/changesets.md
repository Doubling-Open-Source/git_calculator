# Changesets

This repo uses [changesets](https://github.com/changesets/changesets) only to record the **PEP 440** bump (`patch` / `minor` / `major`). Canonical version is `[project].version` in `pyproject.toml`. `package.json` exists so the Changesets CLI can run; release tooling copies that version into `pyproject.toml`.

Release notes are [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) in `CHANGELOG.md` (`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`). After `changeset version`, `scripts/format_changelog.py` rewrites Changesets' Major/Minor/Patch headings to those sections and dates the release as `## [X.Y.Z] - YYYY-MM-DD`.

Do not run `npx changeset init` again.

## One-time local setup

```
npm install
```

## On a feature PR

If the PR changes `src/` or `pyproject.toml`, add a changeset:

```
npx changeset
```

Write the summary as a Keep a Changelog bullet (what the user sees), for example `Add git-calculator --quiet`. Commit the new `.changeset/<id>.md` file.

Bump type maps to changelog sections when the release is cut:

| Changeset | Keep a Changelog |
| --------- | ---------------- |
| major     | Changed          |
| minor     | Added            |
| patch     | Fixed            |

Docs-only and CI-only PRs do not need a changeset. To skip the CI check on an exceptional product PR, add the `skip-changeset` label.

## Releasing

GitHub Releases are cut with `scripts/gh-release.sh` (separate PR). Notes for `gh release` are the Keep a Changelog body for that version, not the default Changesets "Major Changes" dump.
