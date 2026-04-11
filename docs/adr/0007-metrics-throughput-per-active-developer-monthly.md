# ADR 0007: `metrics_throughput_per_active_developer_monthly`

## Status

Not yet approved.

## Context

Monthly **throughput per “active” author** (commits divided by a rolling-window author count) exists in Python as [`calculate_throughput_per_active_developer`](../../src/calculators/throughput_calculator.py). It uses calendar-month buckets from [`extract_commits_and_authors`](../../src/calculators/throughput_calculator.py) and intersects **authors who committed in that month** with **authors who committed in a lookback window** ending at the start of that month.

Related interchange tables:

- [`metrics_throughput_monthly`](../../schema/metrics_throughput_monthly.sql) — raw `commit_count` and `distinct_author_count` only ([ADR 0005](0005-metrics-throughput-monthly.md)).
- [`metrics_throughput_per_active_developer_weekly`](../../schema/metrics_throughput_per_active_developer_weekly.sql) — ISO week grain and intersection semantics ([ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md)).

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Decision

**Table:** [`schema/metrics_throughput_per_active_developer_monthly.sql`](../../schema/metrics_throughput_per_active_developer_monthly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_month`, `weeks_back` | Grain; PK. `period_month` is `YYYY-MM` (localtime `strftime` on `committed_at`), aligned with other monthly metrics — not the legacy unpadded `f"{year}-{month}"` string. |
| `total_commits` | Commits in that calendar month for the repo. |
| `active_authors_in_month` | Size of **intersection**: authors with ≥1 commit in `period_month` ∩ authors with ≥1 commit in the activity window defined for parity with legacy (see below). |
| `throughput_per_active_dev` | `total_commits / active_authors_in_month`, or `0` if denominator is `0`. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Activity window (implementer note):** Legacy Python uses `month_start = datetime(y, m, 1)`, `cutoff = month_start - timedelta(weeks=weeks_back)`, and includes commits with `cutoff <= commit_date <= month_start`, which **only includes the first calendar day** of the month in the upper bound. For interchange, **either** reproduce that bound for strict parity **or** use a clearer window (for example `[cutoff, end_of_month]`) and document the choice in the materialization. The reference `INSERT … SELECT` should state which definition it uses.

**Materialization:** Wire into `validate_schema_metrics` / `schema_metrics.runner` only after parity tests against [`calculate_throughput_per_active_developer`](../../src/calculators/throughput_calculator.py) (or an explicitly documented deviation).

## Personally identifiable information (PII)

Aggregate **per repo × month** — no `author_ref` column. Small `active_authors_in_month` still carries small-`N` re-identification risk ([ADR 0001 — small N](0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates)).

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0005](0005-metrics-throughput-monthly.md), [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md).
