# Metrics SQL stubs (not implemented)

Each stub file’s header starts with **`NOT YET IMPLEMENTED`**. Implemented metrics SQL files start with **`IMPLEMENTED`**.

These stub files define **DDL only** plus comments. They are **not** wired into
`validate_schema_metrics` / `schema_metrics.runner` until materialization and Python parity exist.

| File | Legacy / calculator target | Implemented elsewhere? |
|------|---------------------------|-------------------------|
| `metrics_throughput_per_active_developer_monthly.sql` | `throughput_calculator.calculate_throughput_per_active_developer` | `metrics_throughput_monthly` is raw counts only; `metrics_throughput_per_active_developer_weekly` is weekly ratio |
| `metrics_active_developers_weekly.sql` | `throughput_calculator.calculate_active_developers_by_week` | `metrics_active_developers_monthly` is calendar-month distinct authors only |
| `metrics_author_commit_percentiles.sql` | `commit_analyzer.calculate_percentiles` (author distribution) | No SQL metric yet |
| `metrics_cycle_time_by_branches.sql` | `cycle_time_by_branches` (`BranchLine`, merge strategies, graph output) | Join `commits_export` + `commit_parent_edges` (and ref tips via `refs_export` as needed) |
| `metrics_multi_repo_aggregate.sql` | `multi_repo_calculator` (cross-repo rollups) | Multiple `repo_slug` / `export_id` rows in the interchange; `batch_id`/`cohort_id` TBD for grouping |

**Already implemented** (see each file’s header + `docs/adr/`):  
`metrics_cycle_time_monthly`, `metrics_cycle_time_delta_events`, `metrics_change_failure_monthly`, `metrics_throughput_monthly`, `metrics_active_developers_monthly`, `metrics_throughput_per_active_developer_weekly`.

**Interchange:** Stubs are unimplemented DDL only; when implemented, materializations should use the extracted tables (`commits_export`, `commit_parent_edges`, `refs_export`) and existing repo / export identifiers — no separate mystery schema is required.
