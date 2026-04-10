# ADR 0002: `metrics_change_failure_monthly`

## Status

Not yet approved.

## Context

Downstream charts need a **monthly change-failure-style rate** without storing commit messages. Raw rows live in [`commits_export`](../../schema/commits_export.sql) per [ADR 0001](0001-minimal-commit-storage-schema.md). This table is a **versioned materialization** keyed by `dataset_id` so multiple recomputes can coexist. Shared rules for `dataset_id`, time buckets, and personally identifiable information (PII) tiers: [`schema/metrics_conventions.md`](../../schema/metrics_conventions.md).

## Decision

**Table:** [`schema/metrics_change_failure_monthly.sql`](../../schema/metrics_change_failure_monthly.sql)

| Column | Role |
|--------|------|
| `repo_slug` | Repository scope; matches `commits_export`. |
| `dataset_id` | Materialization run id (UUID, content hash, pipeline id). |
| `period_month` | `YYYY-MM` via `strftime('%Y-%m', committed_at, 'unixepoch', 'localtime')`. |
| `total_commits` | Commits in that month. |
| `fix_like_commits` | Count where **`subject_has_keywords = 1 OR body_has_keywords = 1`**. |
| `rate_percent` | `100.0 * fix_like_commits / total_commits` (0 if total 0), rounded to 0.1. |
| `source_commits_schema_version` | Optional; max or representative `commits_export.schema_version` used. |
| `computed_at` | Unix seconds when the row was written. |
| `tenant_id` | Optional tenant scope. |
| `metrics_schema_version` | Version of *this* table’s semantics (default 1). |

**Primary key:** `(repo_slug, dataset_id, period_month)`.

**Fix-like definition:** OR of the two boolean flags. This **differs** from [`change_failure_calculator.py`](../../src/calculators/change_failure_calculator.py), which scans the **full message** for keywords; parity is approximate unless exporters set flags from the same keyword set applied to `%B`.

## Personally identifiable information (PII)

**No `author_ref`** at this grain. Only counts and rates.

## Source query

See commented **`INSERT … SELECT`** block at the bottom of [`schema/metrics_change_failure_monthly.sql`](../../schema/metrics_change_failure_monthly.sql).

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md) — `commits_export`, keyword flags.
- [git-log](https://git-scm.com/docs/git-log) — time fields underlying `committed_at`.
