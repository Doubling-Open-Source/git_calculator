# ADR 0010: `metrics_cycle_time_by_branches`

## Status

Not yet approved.

## Context

[`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) builds **branch-line** structures (`BranchLine`: merge commit, first-parent walk, merge-parent recursion with strategies `top`, `reverse`, `narrow`, `stop`) for visualization and analysis. That logic today uses live `git_obj` graphs rather than only `commits_export`-backed queries.

Materializing a comparable metric requires **graph inputs**: [`commits_export`](../../schema/commits_export.sql) (including `commit_parent_edges` in the same file), and optionally `refs_export` when branch tips matter ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Source of truth vs SQL

[`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) / **`BranchLine`** **is the source of truth**, including odd traversal or strategy behavior. **SQL** (DDL + reference `SELECT`) is **guidance**; **update SQL** (and tests) to follow legacy whenever they diverge — the schema does not define behavior ahead of legacy.

## Decision

**Table:** [`schema/metrics_cycle_time_by_branches.sql`](../../schema/metrics_cycle_time_by_branches.sql) — **DDL placeholder** until export + materialization cover everything the branch-line algorithm needs (parent ordering, merge detection).

| Column (stub) | Intended role |
|----------------|---------------|
| `branch_line_id` | Stable identifier for one `BranchLine` instance (for example hash of `(merge_sha, strategy, root_sha)` — **define when implementing**). |
| `strategy` | Same vocabulary as Python (`top`, `reverse`, `narrow`, `stop`, …). |
| `root_sha` | Entry commit / merge anchor for the line. |

**Extend the table** when implementing: merge SHA, departure SHA, commit count, optional cycle-time stats for commits on the line, and any fields needed for parity with `BranchLine`’s graph export.

**Computation path:** Prefer a dedicated materialization (Python or SQL) that reads parent edges in repo (`repo_slug`) order and matches legacy traversal order; **do not** claim parity until golden tests exist against [`cycle_time_by_branches`](../../src/calculators/cycle_time_by_branches.py) outputs.

## Implementation (when implemented)

Same expectations as [ADR 0007](0007-metrics-throughput-per-active-developer-monthly.md): **legacy behavior is the source of truth**. The SQLite table reflects that behavior, not an alternate graph model.

- **Parity:** Golden or fixture-based tests comparing exported rows (or a canonical serialization) to legacy output for the same `commits_export` + edges; **minimal formatting** only for stable IDs (`branch_line_id`, hex SHAs) and timestamps.
- **Wiring:** Reference `INSERT … SELECT` in the schema file, `schema_metrics/metrics_cycle_time_by_branches.py`, register in [`runner.py`](../../src/calculators/sqlite_lake/schema_metrics/runner.py) and [`constants.ALL_METRICS`](../../src/calculators/sqlite_lake/schema_metrics/constants.py) when validation is ready; mark SQL `IMPLEMENTED` when materialization and tests land.
- **SQLite helpers:** If date or graph primitives are awkward in pure SQL, small UDFs (like `month_start_unix` / `iso_week_monday_unix` elsewhere) are acceptable when they mirror `datetime` / local-time semantics from legacy code.
- **No duplicate semantics:** Avoid a second branch-line implementation in SQL; extend DDL and SQL until it matches legacy.

## Personally identifiable information (PII)

If future columns include per-commit author refs, follow **author_ref-only** rules ([ADR 0001](0001-minimal-commit-storage-schema.md)); aggregate-only columns keep PII lower.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0003](0003-metrics-cycle-time-monthly.md).
