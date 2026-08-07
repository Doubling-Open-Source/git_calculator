# ADR 0006: `metrics_throughput_per_active_developer_weekly`

## Status

Not yet approved.

## Context

Weekly **repo-level** throughput normalized by a rolling “active developer” count is implemented in Python as [`calculate_throughput_per_active_developer_by_week`](../../src/calculators/throughput_calculator.py) (uses [`extract_commits_and_authors_by_week`](../../src/calculators/throughput_calculator.py) for ISO week totals, then a lookback window and `commits / active_authors_in_week`). The prior ADR draft (`metrics_author_commit_weekly`, per-author × week counts) did not match that legacy function; this ADR replaces it with a table aligned to the legacy behavior.

Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Decision

**Table:** [`schema/metrics_throughput_per_active_developer_weekly.sql`](../../schema/metrics_throughput_per_active_developer_weekly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_week`, `weeks_back` | Grain; PK. `period_week` is ISO `YYYY-Www` (same label as `commits_export.period_week`, exporter-aligned to legacy `isocalendar`). |
| `total_commits` | Commits in that ISO week (same count as legacy week bucket). |
| `active_authors_in_week` | Legacy intersection: authors with a commit this week who also have any commit in `[Monday − weeks_back weeks, next Monday]` (local). |
| `throughput_per_active_dev` | `total_commits / active_authors_in_week`, or `0` if denominator is `0`. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Materialization:** Portable SQL reads `commits_export.period_week`, `week_monday_unix`, and `week_end_unix` (next Monday via exporter `timedelta(days=7)`). Lookback uses `local_days_shift` (same timedelta semantics). Do not use fixed `N*7*86400` across DST.

## Personally identifiable information (PII)

This table is **aggregate per repo × week** — **no** `author_ref` column. Re-identification risk is lower than per-author weekly series; still treat small-`N` repos with care for publication.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md).
