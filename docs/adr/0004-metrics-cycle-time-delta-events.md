# ADR 0004: `metrics_cycle_time_delta_events`

## Status

Not yet approved.

## Context

Some analyses need **event-level** cycle times (each gap between consecutive commits by the same contributor), not only monthly aggregates ([ADR 0003](0003-metrics-cycle-time-monthly.md)). Source rows: [`commits_export`](../../schema/commits_export.sql) per [ADR 0001](0001-minimal-commit-storage-schema.md).

## Decision

**Table:** [`schema/metrics_cycle_time_delta_events.sql`](../../schema/metrics_cycle_time_delta_events.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id` | Scope and materialization id. |
| `author_ref` | Partition key for `LAG` (same as lake `author_email` role). |
| `committed_at` | Unix seconds of the **child** commit (end of the gap). |
| `child_sha` | Child commit; part of PK to disambiguate same-second commits. |
| `cycle_minutes` | `(committed_at - prev_committed_at) / 60`, rounded to 2 decimals (lake style). |
| `prev_sha` | Previous commit in author order (optional audit). |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Primary key:** `(repo_slug, dataset_id, author_ref, committed_at, child_sha)`.

**Ordering:** `PARTITION BY author_ref ORDER BY log_ordinal DESC` on [`commits_export`](../../schema/commits_export.sql) — `log_ordinal` follows git_log (newest-first); DESC makes LAG walk oldest→newest like Python’s positive deltas. The lake `commits` SQL path remains `ORDER BY committed_date, sha` until a sequence column exists there.

## Personally identifiable information (PII) (**medium sensitivity**)

This table carries **`author_ref`** plus timestamps. It does **not** store `author_label_pii` or email. Risk: **timing / pattern fingerprinting** and linkage when combined with other data. Interpretation depends on source **`pii_protection_profile`** on `commits_export` ([ADR 0001](0001-minimal-commit-storage-schema.md)). See also [Pseudonyms are not anonymity guarantees](0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates) in ADR 0001.

## Source query

Commented **`INSERT … SELECT`** in [`schema/metrics_cycle_time_delta_events.sql`](../../schema/metrics_cycle_time_delta_events.sql).

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md), [ADR 0003](0003-metrics-cycle-time-monthly.md).
