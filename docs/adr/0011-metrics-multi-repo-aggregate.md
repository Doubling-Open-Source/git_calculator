# ADR 0011: `metrics_multi_repo_aggregate`

## Status

Not yet approved.

## Context

[`MultiRepoCalculator`](../../src/calculators/multi_repo_calculator.py) aggregates **already-computed per-repo metrics** (cycle time, failure rate, throughput, throughput-per-active-dev weekly, cross-repo unique authors, and JSON/composite exports). Inputs are keyed by repository name and in-memory metric dicts — not the per-repo interchange tables directly.

The stub [`schema/metrics_multi_repo_aggregate.sql`](../../schema/metrics_multi_repo_aggregate.sql) stores **cross-repo rollups** in a generic key/value shape so dashboards can snapshot “this cohort of exports / this batch run” without re-scanning every repo.

## Decision

**Table:** [`schema/metrics_multi_repo_aggregate.sql`](../../schema/metrics_multi_repo_aggregate.sql)

| Column | Role |
|--------|------|
| `batch_id` | Identifies one aggregation run (pipeline id, content hash, or operator-defined batch). |
| `cohort_id` | Logical group being summarized (team, program, or fixed list of `repo_slug`s / exports). |
| `metric_name` | Namespaced key (for example `aggregate_cycle_time.monthly_avg_p75`, `throughput.total_commits`). |
| `period_key` | Time bucket aligned with source metrics (`YYYY-MM`, `YYYY-Www`, or `all`). |
| `value_real` | Scalar when the aggregate is a single float. |
| `value_json` | JSON for structured payloads (multi-column averages, nested series). |
| Lineage | `source_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Semantics:** Mirror [`aggregate_cycle_time_metrics`](../../src/calculators/multi_repo_calculator.py), [`aggregate_failure_rate_metrics`](../../src/calculators/multi_repo_calculator.py), [`aggregate_throughput_metrics`](../../src/calculators/multi_repo_calculator.py), [`aggregate_throughput_per_active_dev_metrics`](../../src/calculators/multi_repo_calculator.py), and related helpers — **mean across repos** per month/week unless an existing function documents otherwise.

**Inputs:** Consumers load per-repo metric rows (each with `repo_slug`, `dataset_id` / `export_id`) from interchange snapshots, then write one aggregate row set per `(batch_id, cohort_id)`.

## Personally identifiable information (PII)

Designed for **aggregates**. Do not store per-author fields in `value_json` unless policy allows; prefer upstream per-repo tables that already enforce `author_ref` rules.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md).
