# ADR 0009: `metrics_author_commit_percentiles`

## Status

Not yet approved.

## Context

[`commit_analyzer.calculate_percentiles`](../../src/calculators/commit_analyzer.py) ranks authors by **total commit count** (summed over time buckets in `commits_by_author`) using pandas `Series.rank(method="max")`, then maps each author to `(rank / N) * 100` where `N` is the number of authors. It answers “how concentrated are commits across authors?” for charting, not cycle-time percentiles.

The stub [`schema/metrics_author_commit_percentiles.sql`](../../schema/metrics_author_commit_percentiles.sql) carries **`author_ref`**, so it is a **medium–high PII** surface compared to repo-level aggregates.

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

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

## Personally identifiable information (PII)

**Per-author rows.** Suitable for trusted analytics pipelines; avoid publishing wide extracts for small repos without policy review.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0004](0004-metrics-cycle-time-delta-events.md).
