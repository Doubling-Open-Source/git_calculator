# Metrics SQL stubs (status)

There are currently **no stub-only** metric SQL files under `schema/`.

Each metrics SQL file’s header starts with **`IMPLEMENTED`** or **`NOT YET IMPLEMENTED`**.
ADRs under `docs/adr/` plus those headers are the source of truth for what ships.

Notable opt-in / non-`METRIC_ALL` paths:

- **`metrics_cycle_time_by_branches`** ([ADR 0010](../docs/adr/0010-metrics-cycle-time-by-branches.md)): Python→table round-trip; explicit `--metric cycle_time_by_branches` only (not in `ALL_METRICS` / `METRIC_ALL`).
- **`metrics_multi_repo_aggregate`** ([ADR 0011](../docs/adr/0011-metrics-multi-repo-aggregate.md)): Python materialization over dict inputs; not in `ALL_METRICS`.

**Interchange:** Materializations use `commits_export`, `commit_parent_edges`, and `refs_export` as needed.
