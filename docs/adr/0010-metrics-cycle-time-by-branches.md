# ADR 0010: `metrics_cycle_time_by_branches`

## Status

Not yet approved.

## Context

[`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) builds **branch-line** structures (`BranchLine`: merge commit, first-parent walk, merge-parent recursion with strategies `top`, `reverse`, `narrow`, `stop`) for visualization and analysis. That logic today uses live `git_obj` graphs, not the SQLite interchange alone.

Materializing a comparable metric requires **graph inputs**: [`commits_export`](../../schema/commits_export.sql) (including `commit_parent_edges` in the same file), and optionally `refs_export` when branch tips matter ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Decision

**Table:** [`schema/metrics_cycle_time_by_branches.sql`](../../schema/metrics_cycle_time_by_branches.sql) — **DDL placeholder** until the interchange exposes everything the branch-line algorithm needs (parent ordering, merge detection).

| Column (stub) | Intended role |
|----------------|---------------|
| `branch_line_id` | Stable identifier for one `BranchLine` instance (for example hash of `(merge_sha, strategy, root_sha)` — **define when implementing**). |
| `strategy` | Same vocabulary as Python (`top`, `reverse`, `narrow`, `stop`, …). |
| `root_sha` | Entry commit / merge anchor for the line. |

**Extend the table** when implementing: merge SHA, departure SHA, commit count, optional cycle-time stats for commits on the line, and any fields needed for parity with `BranchLine`’s graph export.

**Computation path:** Prefer a dedicated materialization (Python or SQL) that reads parent edges in repo (`repo_slug`) order and matches legacy traversal order; **do not** claim parity until golden tests exist against [`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) outputs.

## Personally identifiable information (PII)

If future columns include per-commit author refs, follow **author_ref-only** rules ([ADR 0001](0001-minimal-commit-storage-schema.md)); aggregate-only columns keep PII lower.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0003](0003-metrics-cycle-time-monthly.md).
