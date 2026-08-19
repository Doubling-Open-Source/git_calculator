# Changesets

Config lives in this directory (already initialized). Do not run `npx changeset init` again.

- First GitHub Release of the version on `main`: `scripts/gh-release.sh --current`
- Later: `npx changeset` on the PR, then `scripts/gh-release.sh`

See `docs/releasing.md`.
