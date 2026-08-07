# ADR 0009: `metrics_author_commit_percentiles`

## Status

Not yet approved.

## Context

[`commit_analyzer.calculate_percentiles`](../../src/calculators/commit_analyzer.py) ranks authors by **total commit count** (summed over time buckets in `commits_by_author`) using pandas `Series.rank(method="max")`, then maps each author to `(rank / N) * 100` where `N` is the number of authors. It answers “how concentrated are commits across authors?” for charting, not cycle-time percentiles.

The stub [`schema/metrics_author_commit_percentiles.sql`](../../schema/metrics_author_commit_percentiles.sql) carries **`author_ref`**, so it is a **medium–high PII** surface compared to repo-level aggregates.

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Source of truth vs SQL

**Legacy** [`calculate_percentiles`](../../src/calculators/commit_analyzer.py) (and how upstream code builds `commits_by_author`) **is the source of truth**. **SQL** is **guidance** for schema and materialization; update SQL and validation to follow legacy, including pandas `rank` behavior and edge cases.

## Decision

**Table:** [`schema/metrics_author_commit_percentiles.sql`](../../schema/metrics_author_commit_percentiles.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `as_of_period`, `author_ref` | Grain; PK. `as_of_period` scopes the snapshot (for example `YYYY-MM` for a monthly rollup, or a sentinel like `all` / dataset-scoped “full history” — **finalize in materialization** and document the chosen semantics). |
| `commit_count` | Total commits for that author in the `as_of_period` scope. |
| `author_commit_percentile` | Percentile in `[0, 100]` matching legacy `rank(method="max") / N * 100` over authors in that scope. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Rules:**

- Store **`author_ref` only** — never raw email or `author_label_pii` ([ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0004](0004-metrics-cycle-time-delta-events.md) PII posture).
- **Finalize `as_of_period` meaning** before turning on `validate_schema_metrics`: one table can support either monthly windows or a single export-wide snapshot, but not ambiguous mixed keys.

## Implementation (when implemented)

Align with [ADR 0007](0007-metrics-throughput-per-active-developer-monthly.md) style: **one** set of numbers — legacy [`calculate_percentiles`](../../src/calculators/commit_analyzer.py) (and the same upstream `commits_by_author` / export inputs the legacy path uses), plus **minimal formatting** only in the table and in canonical comparison (e.g. fixed `YYYY-MM` for month-scoped rows if legacy uses unpadded month keys elsewhere).

- **Legacy parity:** Validation should call the existing calculator (or a thin wrapper that only reshapes output), then compare row-by-row to the materialization `SELECT`. On mismatch, **change SQL** to match legacy.
- **Module wiring:** `schema_metrics/metrics_author_commit_percentiles.py`, commented reference `INSERT … SELECT` in [`schema/metrics_author_commit_percentiles.sql`](../../schema/metrics_author_commit_percentiles.sql), [`runner.py`](../../src/calculators/sqlite_lake/schema_metrics/runner.py) + [`constants.py`](../../src/calculators/sqlite_lake/schema_metrics/constants.py), tests under `tests/test_metrics_author_commit_percentiles.py` (or equivalent).
- **PII:** Keep **`author_ref` only** in the table; validation and docs stay explicit that this is higher sensitivity than repo-level aggregates ([ADR 0004](0004-metrics-cycle-time-delta-events.md)).

## Personally identifiable information (PII)

**Per-author rows.** Suitable for trusted analytics pipelines; avoid publishing wide extracts for small repos without policy review.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0004](0004-metrics-cycle-time-delta-events.md).
