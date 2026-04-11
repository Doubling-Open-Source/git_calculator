"""
Metric ids for ``validate_schema_metrics_for_logs`` and the validation CLI.

Each id matches the stem of ``schema/metrics_<id>.sql`` where applicable
(``cycle_time_monthly`` ↔ ``metrics_cycle_time_monthly.sql``).
``METRIC_MULTI_REPO_AGGREGATE`` is validated from dict fixtures only (not in ``ALL_METRICS``).
"""

from __future__ import annotations

METRIC_CYCLE_TIME_MONTHLY = "cycle_time_monthly"
METRIC_CHANGE_FAILURE_MONTHLY = "change_failure_monthly"
METRIC_THROUGHPUT_MONTHLY = "throughput_monthly"
METRIC_ACTIVE_DEVELOPERS_MONTHLY = "active_developers_monthly"
METRIC_ACTIVE_DEVELOPERS_WEEKLY = "active_developers_weekly"
METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_WEEKLY = "throughput_per_active_developer_weekly"
METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_MONTHLY = "throughput_per_active_developer_monthly"
METRIC_CYCLE_TIME_DELTA_EVENTS = "cycle_time_delta_events"
METRIC_AUTHOR_COMMIT_PERCENTILES = "author_commit_percentiles"
METRIC_CYCLE_TIME_BY_BRANCHES = "cycle_time_by_branches"
# Dict-based validation only (not in ``ALL_METRICS`` / ``validate_schema_metrics_for_logs``).
METRIC_MULTI_REPO_AGGREGATE = "multi_repo_aggregate"
METRIC_ALL = "all"

# Order is fixed: ``runner._PIPELINE`` must stay aligned (see module-level assert there).
ALL_METRICS: tuple[str, ...] = (
    METRIC_CYCLE_TIME_MONTHLY,
    METRIC_CHANGE_FAILURE_MONTHLY,
    METRIC_THROUGHPUT_MONTHLY,
    METRIC_ACTIVE_DEVELOPERS_MONTHLY,
    METRIC_ACTIVE_DEVELOPERS_WEEKLY,
    METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_WEEKLY,
    METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_MONTHLY,
    METRIC_CYCLE_TIME_DELTA_EVENTS,
    METRIC_AUTHOR_COMMIT_PERCENTILES,
    METRIC_CYCLE_TIME_BY_BRANCHES,
)
