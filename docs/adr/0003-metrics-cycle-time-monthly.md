# ADR 0003: `metrics_cycle_time_monthly`

## Status

Not yet approved.

## Context

Cycle-time charts need **monthly aggregates** of inter-commit gaps (minutes), matching the semantics of [`sqlite_lake` `query_by_month_stats_pure_sql`](../../src/calculators/sqlite_lake/cycle_time_by_commits_calculator.py): `LAG` partitioned by **author**, ordered by **`committed_at`**, `sha`; then all non-null deltas pooled and grouped by **calendar month of the child commit** (`strftime` localtime).

## Decision

**Table:** [`schema/metrics_cycle_time_monthly.sql`](../../schema/metrics_cycle_time_monthly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_month` | Grain; PK with `period_month` = `YYYY-MM`. |
| `sample_count` | Number of delta samples in that month (`n` in bucket_meta; months with `n < 2` **omitted**). |
| `sum_cycle_minutes`, `avg_cycle_minutes` | Sum and mean of `cycle_minutes`. |
| `p75_cycle_minutes` | Linear interpolation of p75 on sorted deltas (same formula as lake SQL). |
| `std_cycle_minutes` | Sample standard deviation (integer rounded, as in lake). |
| `source_commits_schema_version`, `computed_at`, `tenant_id` | Lineage. |
| `metrics_schema_version` | Version of this metric table (default 1). |

**No `author_ref`** in this table—repo-wide monthly stats only.

## Personally identifiable information (PII)

Aggregate only; no per-author columns.

## Source query

Full CTE chain is in the comment block in [`schema/metrics_cycle_time_monthly.sql`](../../schema/metrics_cycle_time_monthly.sql). Bind `repo_slug`, `dataset_id`, `computed_at`, and optional lineage fields when wrapping as `INSERT INTO … SELECT`.

## Computation notes

- Months with fewer than **two** delta samples in `with_month` are excluded (`HAVING COUNT(*) >= 2`).
- Ordering tie-break **`sha`** matches lake SQL for stable LAG pairing when timestamps collide.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md) — `commits_export.author_ref`, `committed_at`, `sha`.
