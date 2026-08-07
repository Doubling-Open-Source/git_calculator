# Metrics SQL stubs (not implemented)

Each stub file’s header starts with **`NOT YET IMPLEMENTED`**. Implemented metrics SQL files start with **`IMPLEMENTED`**.

Stub files define **DDL only** plus comments. They are **not** wired into
`validate_schema_metrics` / `schema_metrics.runner` until materialization and Python validation exist.

There are currently **no stub-only** metric SQL files under `schema/`.

**Already implemented** (see each file’s header + `docs/adr/`):

| File | ADR | Notes |
|------|-----|--------|
| `metrics_cycle_time_monthly` | 0003 | SQL materialization + Python parity |
| `metrics_cycle_time_delta_events` | — | SQL + Python parity |
| `metrics_change_failure_monthly` | 0002 | SQL + Python parity |
| `metrics_throughput_monthly` | — | SQL + Python parity |
| `metrics_active_developers_monthly` | 0004 | SQL + Python parity |
| `metrics_active_developers_weekly` | 0008 | SQL + Python parity |
| `metrics_throughput_per_active_developer_weekly` | 0006 | SQL + Python parity |
| `metrics_throughput_per_active_developer_monthly` | 0007 | SQL + Python parity |
| `metrics_author_commit_percentiles` | 0009 | SQL + Python parity |
| `metrics_cycle_time_by_branches` | [0010](../docs/adr/0010-metrics-cycle-time-by-branches.md) | **Python-materialized** table; round-trip check (not independent SQL graph) |
| `metrics_multi_repo_aggregate` | [0011](../docs/adr/0011-metrics-multi-repo-aggregate.md) | Python materialization, dict inputs (not in `ALL_METRICS`) |

**Interchange:** Materializations use `commits_export`, `commit_parent_edges`, and `refs_export` as needed — no separate mystery schema.
