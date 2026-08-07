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

## Source of truth vs SQL

**Legacy Python** ([`calculate_active_developers_by_week`](../../src/calculators/throughput_calculator.py) and helpers) **is the source of truth**, quirks included. **SQL** DDL and reference `SELECT` are **guidance**; they must be revised to mirror legacy when they drift.

## Decision

**Table:** [`schema/metrics_active_developers_weekly.sql`](../../schema/metrics_active_developers_weekly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_week`, `weeks_back` | Grain; PK. `period_week` is ISO `YYYY-Www` from `commits_export`, same labeling as [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md). |
| `total_commits` | Commits whose `committed_at` falls in that ISO week (same week bucket as legacy `extract_commits_and_authors_by_week`). |
| `active_developer_count` | `COUNT(DISTINCT author_ref)` over authors with ≥1 commit in `[week_monday − weeks_back weeks, week_end]` local — matching legacy `timedelta`; SQL uses `week_end_unix` + `local_days_shift` (not `N*7*86400`). |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Materialization:** Same portable week columns on `commits_export` as ADR 0006 so week boundaries match [`metrics_throughput_per_active_developer_weekly`](../../schema/metrics_throughput_per_active_developer_weekly.sql).

## Implementation (when implemented)

Follow the same pattern as [ADR 0007](0007-metrics-throughput-per-active-developer-monthly.md) and existing `schema_metrics` modules ([`metrics_throughput_per_active_developer_weekly`](../../src/calculators/sqlite_lake/schema_metrics/metrics_throughput_per_active_developer_weekly.py)):

- **Legacy parity:** Materialization `INSERT … SELECT` and `validate_active_developers_weekly_for_logs` must match [`calculate_active_developers_by_week`](../../src/calculators/throughput_calculator.py) (same week buckets as [`extract_commits_and_authors_by_week`](../../src/calculators/throughput_calculator.py), same rolling-window author count), **including legacy quirks**. If tests show SQL and Python differ, fix SQL. Do not introduce a second definition of the metric under another name.
- **Minimal formatting:** `period_week` in the table should be **`YYYY-Www`** (local ISO week), aligned with `commits_export.period_week` and any canonical validation rows. If legacy helpers emit labels that differ only by padding, normalize in one place (as monthly metrics normalize `YYYY-M` → `YYYY-MM`).
- **Wiring:** Add `schema/metrics_active_developers_weekly.sql` reference `SELECT`, [`metrics_active_developers_weekly.py`](../../src/calculators/sqlite_lake/schema_metrics/) validation, register in [`runner.py`](../../src/calculators/sqlite_lake/schema_metrics/runner.py) and [`constants.ALL_METRICS`](../../src/calculators/sqlite_lake/schema_metrics/constants.py), document the header in the SQL file (`IMPLEMENTED` when done).
- **Tests:** TDD-friendly unit tests on synthetic `commits_export` rows (see [`tests/schema_metrics_fixtures.py`](../../tests/schema_metrics_fixtures.py)); optional run via [`scripts/validate_schema_metrics.py`](../../scripts/validate_schema_metrics.py) on local clones.

## Personally identifiable information (PII)

Aggregate counts only — no `author_ref` in the table.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md).
