# Metrics SQL stubs (not implemented)

Each stub file’s header starts with **`NOT YET IMPLEMENTED`**. Implemented metrics SQL files start with **`IMPLEMENTED`**.

These stub files define **DDL only** plus comments. They are **not** wired into
`validate_schema_metrics` / `schema_metrics.runner` until materialization and Python parity exist.

| File | ADR | Legacy / calculator target | Implemented elsewhere? |
|------|-----|---------------------------|-------------------------|
| `metrics_author_commit_percentiles.sql` | [0009](../docs/adr/0009-metrics-author-commit-percentiles.md) | `commit_analyzer.calculate_percentiles` (author distribution) | No SQL metric yet |
| `metrics_cycle_time_by_branches.sql` | [0010](../docs/adr/0010-metrics-cycle-time-by-branches.md) | `cycle_time_by_branches` (`BranchLine`, merge strategies, graph output) | Join `commits_export` + `commit_parent_edges` (and ref tips via `refs_export` as needed) |
| `metrics_multi_repo_aggregate.sql` | [0011](../docs/adr/0011-metrics-multi-repo-aggregate.md) | `multi_repo_calculator` (cross-repo rollups) | Multiple `repo_slug` / `export_id` rows in the interchange; `batch_id`/`cohort_id` TBD for grouping |

**Already implemented** (see each file’s header + `docs/adr/`):  
`metrics_cycle_time_monthly`, `metrics_cycle_time_delta_events`, `metrics_change_failure_monthly`, `metrics_throughput_monthly`, `metrics_active_developers_monthly`, `metrics_active_developers_weekly` ([0008](../docs/adr/0008-metrics-active-developers-weekly.md)), `metrics_throughput_per_active_developer_weekly`, `metrics_throughput_per_active_developer_monthly` ([0007](../docs/adr/0007-metrics-throughput-per-active-developer-monthly.md)).

**Interchange:** Stubs are unimplemented DDL only; when implemented, materializations should use the extracted tables (`commits_export`, `commit_parent_edges`, `refs_export`) and existing repo / export identifiers — no separate mystery schema is required.
