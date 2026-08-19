# Work style

Operators declare how the repository lands changes. That choice sets both the **commit set** for a run and how **change-failure** treats a squash-merge message. They do not choose subject vs body flags.

## Contract

| Work style | Commit set | Change-failure signal |
| --- | --- | --- |
| `all-branches` (default) | Every commit reachable from all refs and reflogs | Fix-like if the summary or the body matches the keyword set |
| `squash` | Commits reachable from the [default branch](../glossary/default-branch.md) only | Fix-like if the summary matches the keyword set; the body is ignored |

## Acceptance

- Unknown work-style values fail closed.
- `all-branches` preserves prior rates for the same clone.
- Under `squash`, a mainline commit whose body contains a fix keyword and whose summary does not is **not** fix-like.
- Under `squash`, a commit reachable only from a topic branch is **not** in totals or rates.
- Schema materialization for `squash` uses the existing summary keyword flag; it does not store a second scan-mode column.

Keyword strings themselves are unchanged.
