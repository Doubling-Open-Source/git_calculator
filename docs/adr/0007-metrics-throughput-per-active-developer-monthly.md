# ADR 0007: `metrics_throughput_per_active_developer_monthly`

## Status

Not yet approved.

## Context

Monthly throughput per active developer is defined by legacy [`calculate_throughput_per_active_developer`](../../src/calculators/throughput_calculator.py): calendar months from [`extract_commits_and_authors`](../../src/calculators/throughput_calculator.py), intersection with authors having commits in `cutoff <= commit_date <= month_start` (`month_start` = first day 00:00 local).

Related metrics tables: [`metrics_throughput_monthly`](../../schema/metrics_throughput_monthly.sql) ([ADR 0005](0005-metrics-throughput-monthly.md)), [`metrics_throughput_per_active_developer_weekly`](../../schema/metrics_throughput_per_active_developer_weekly.sql) ([ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md)).

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Source of truth vs SQL

**Legacy Python is the source of truth** — in this case [`calculate_throughput_per_active_developer`](../../src/calculators/throughput_calculator.py) and its helpers, including any **quirks or odd behaviors** (e.g. inclusive bounds, month-key padding in dicts).

The **SQL** (`schema/metrics_*.sql`: DDL plus commented reference `INSERT … SELECT`) is **guidance** for implementers and for interchange shape. When legacy and SQL disagree, **update the SQL** (and validation) to follow legacy — not the other way around unless legacy is intentionally changed in code with tests.

## Decision

**Table:** [`schema/metrics_throughput_per_active_developer_monthly.sql`](../../schema/metrics_throughput_per_active_developer_monthly.sql)

Materialization and [`validate_throughput_per_active_developer_monthly_for_logs`](../../src/calculators/sqlite_lake/schema_metrics/metrics_throughput_per_active_developer_monthly.py) match legacy numbers. **Formatting only:** `period_month` is `YYYY-MM` in the table and in canonical validation rows; legacy dict keys use unpadded months (`YYYY-M`) — normalized with the same helper as [`metrics_throughput_monthly`](../../src/calculators/sqlite_lake/schema_metrics/metrics_throughput_monthly.py).

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_month`, `weeks_back` | Grain; PK. |
| `total_commits`, `active_authors_in_month`, `throughput_per_active_dev` | Same definitions as legacy. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

## Personally identifiable information (PII)

Aggregate **per repo × month** — no `author_ref` column ([ADR 0001 — small N](0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates)).

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0005](0005-metrics-throughput-monthly.md), [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md).
