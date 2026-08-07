# ADR 0005: `metrics_throughput_monthly`

## Status

Not yet approved.

## Context

Dashboards need **monthly throughput**: how many commits landed and how many distinct contributors (`author_ref`) were active, without listing individuals. Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)).

## Decision

**Table:** [`schema/metrics_throughput_monthly.sql`](../../schema/metrics_throughput_monthly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_month` | Grain; `period_month` = `YYYY-MM` via `strftime(..., 'localtime')`. |
| `commit_count` | Rows in `commits_export` for that repo/month. |
| `distinct_author_count` | `COUNT(DISTINCT author_ref)` in that month. |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**No per-author columns** — only counts.

## Personally identifiable information (PII)

Aggregate counts only; no author identifiers in this table. Small teams: **low `distinct_author_count`** can still imply who contributed (see [ADR 0001 — pseudonyms and small N](0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates)).

## Source query

Commented `INSERT … SELECT` in [`schema/metrics_throughput_monthly.sql`](../../schema/metrics_throughput_monthly.sql).

## Computation notes

- Month bucketing matches other monthly metrics (localtime `strftime` on `committed_at`).
- Related app logic may also live in [`throughput_calculator.py`](../../src/calculators/throughput_calculator.py) for multi-repo summaries; this table is **per-repo** interchange.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md).
