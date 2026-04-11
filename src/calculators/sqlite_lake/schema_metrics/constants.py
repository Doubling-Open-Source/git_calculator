"""
Metric ids for ``validate_schema_metrics_for_logs`` and the validation CLI.

Each id matches the stem of ``schema/metrics_<id>.sql`` where applicable
(``cycle_time_monthly`` ↔ ``metrics_cycle_time_monthly.sql``).
"""

from __future__ import annotations

METRIC_CYCLE_TIME_MONTHLY = "cycle_time_monthly"
METRIC_CHANGE_FAILURE_MONTHLY = "change_failure_monthly"
METRIC_THROUGHPUT_MONTHLY = "throughput_monthly"
METRIC_ACTIVE_DEVELOPERS_MONTHLY = "active_developers_monthly"
METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_WEEKLY = "throughput_per_active_developer_weekly"
METRIC_CYCLE_TIME_DELTA_EVENTS = "cycle_time_delta_events"
METRIC_ALL = "all"

# Order is fixed: ``runner._PIPELINE`` must stay aligned (see module-level assert there).
ALL_METRICS: tuple[str, ...] = (
    METRIC_CYCLE_TIME_MONTHLY,
    METRIC_CHANGE_FAILURE_MONTHLY,
    METRIC_THROUGHPUT_MONTHLY,
    METRIC_ACTIVE_DEVELOPERS_MONTHLY,
    METRIC_THROUGHPUT_PER_ACTIVE_DEVELOPER_WEEKLY,
    METRIC_CYCLE_TIME_DELTA_EVENTS,
)
