# ADR 0008: `metrics_active_developers_weekly`

## Status

Not yet approved.

## Context

Per **ISO week**, legacy [`calculate_active_developers_by_week`](../../src/calculators/throughput_calculator.py) returns:

1. Total commits in that week.
2. Count of distinct authors who committed **anywhere in the rolling lookback window** ending at the end of that ISO week (not an intersection with authors-only-in-that-week).
3. (Python only) the set of those author emails.

[`metrics_active_developers_monthly`](../../schema/metrics_active_developers_monthly.sql) is calendar-month distinct authors only. [`metrics_throughput_per_active_developer_weekly`](../../schema/metrics_throughput_per_active_developer_weekly.sql) uses **intersection** semantics for the denominator — different from this series.

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Decision

**Table:** [`schema/metrics_active_developers_weekly.sql`](../../schema/metrics_active_developers_weekly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_week`, `weeks_back` | Grain; PK. `period_week` is ISO `YYYY-Www` (local `%G`/`%V`), same labeling as [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md). |
| `total_commits` | Commits whose `committed_at` falls in that ISO week (same week bucket as legacy `extract_commits_and_authors_by_week`). |
| `active_developer_count` | `COUNT(DISTINCT author_ref)` over authors with ≥1 commit in `[week_monday − weeks_back weeks, week_monday + 7 days)` in local time — matching legacy `cutoff_date` through `week_date + timedelta(days=7)`. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Materialization:** Prefer reusing the same ISO-week helpers as ADR 0006 (`iso_week_monday_unix` or equivalent) so week boundaries match [`metrics_throughput_per_active_developer_weekly`](../../schema/metrics_throughput_per_active_developer_weekly.sql).

## Personally identifiable information (PII)

Aggregate counts only — no `author_ref` in the table.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md).
