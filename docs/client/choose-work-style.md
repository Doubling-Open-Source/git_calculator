# Choose work style

Pick **work style** from how the team merges, not from how metrics count keywords.

Use **`all-branches`** (the default) when feature branches and merge commits are part of the history you care about. Change-failure looks at the full commit message.

Use **`squash`** when work lands as squash commits on the default branch (usually `main`). The run follows that branch only. Change-failure uses the squash **summary** (the PR title line) and ignores the concatenated PR body, so a leftover “fix” from an earlier commit in the squash does not inflate the rate.

Pass `--work-style squash` on `git-calculator single`. Omit the flag or pass `--work-style all-branches` for the default. Under squash, `--default-branch` overrides which ref is followed when auto-detection is wrong for CI.

Contract: [work style](../features/work-style.md).
