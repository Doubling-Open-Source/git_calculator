# Changesets

This repo uses [changesets](https://github.com/changesets/changesets) to record **patch / minor / major** bumps. `.changeset/config.json` and `package.json` (`git-calculator` at version `2.0.0`) are the integration — do not run `npx changeset init`.

## One-time local setup

```
npm install
```

## On a feature PR

If the PR changes `src/` or `pyproject.toml`, add a changeset before merge:

```
npx changeset
```

Commit the new `.changeset/<id>.md` file. Docs-only and CI-only PRs do not need one. To skip the CI check on an exceptional product PR, add the `skip-changeset` label.

## Releasing

Cutting a GitHub Release is a separate script (`scripts/gh-release.sh`, once that lands). This PR only installs the changeset toolchain and the PR check.
