# ADR 0010: `metrics_cycle_time_by_branches`

## Status

Accepted (Python-materialized table; storage round-trip validated).

## Context

[`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) builds **branch-line** structures (`BranchLine`: merge commit, first-parent walk, merge-parent recursion with strategies `top`, `reverse`, `narrow`, `stop`) for visualization and analysis. That logic uses live `git_obj` graphs rather than a pure-SQL graph walk.

Materializing comparable rows requires **graph inputs**: [`commits_export`](../../schema/commits_export.sql) including `commit_parent_edges` ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Source of truth vs SQL

[`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) / **`BranchLine`** **is the source of truth**. The SQLite table stores a serialization of those lines. Validation writes rows from Python and reads them back — that checks **materialization / round-trip**, **not** an independent SQL implementation of the graph algorithm. Do not treat runner success as “SQL parity with BranchLine.”

## Decision

**Table:** [`schema/metrics_cycle_time_by_branches.sql`](../../schema/metrics_cycle_time_by_branches.sql) — **IMPLEMENTED** as Python materialization (`schema_metrics/metrics_cycle_time_by_branches.py`), wired in `ALL_METRICS` / `runner.py`.

| Column | Role |
|--------|------|
| `branch_line_id` | SHA-256 hex of `(strategy, merge_sha, root_sha)` |
| `strategy` | Same vocabulary as Python (`top`, `reverse`, `narrow`, `stop`, …) |
| `root_sha` / `merge_sha` / `departure_sha` | Line anchors from `BranchLine` |
| `commit_count`, `*_seconds` | Counts / cycle phases from legacy |

**Validation:** Requires `commit_parent_edges` for the repo. Missing edges is an **error** (not a silent skip). With edges present, compare Python canonical lines to SELECT readback after Python write.

## Personally identifiable information (PII)

Aggregate / SHA-bearing columns only; follow **author_ref-only** rules if author fields are added later ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0003](0003-metrics-cycle-time-monthly.md).
