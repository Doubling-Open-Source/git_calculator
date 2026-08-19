# default branch

The branch squash-style analysis follows: `main` if it exists, otherwise `master`, otherwise the target of `origin/HEAD`. Operators may override that detection with `--default-branch`. Commits only on other branches are out of the squash commit set.
