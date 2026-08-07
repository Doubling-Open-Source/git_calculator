"""
Metric ids for ``validate_schema_metrics_for_logs`` and the validation CLI.

Each id matches the stem of ``schema/metrics_<id>.sql`` where applicable
(``cycle_time_monthly`` ↔ ``metrics_cycle_time_monthly.sql``).

``ALL_METRICS``: SQL↔legacy parity metrics run under ``METRIC_ALL``.
``OPT_IN_METRICS``: explicit ``--metric <id>`` only (not in ``METRIC_ALL``).
``METRIC_MULTI_REPO_AGGREGATE``: dict-fixture validation only (not in either list).

Batch 1 foundation: id constants exist so later PRs can register validators;
``ALL_METRICS`` / ``OPT_IN_METRICS`` stay empty until metric modules land.
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
ALL_METRICS: tuple[str, ...] = ()

# Explicit ``--metric`` only: Python-materialized round-trip, not SQL↔legacy parity.
OPT_IN_METRICS: tuple[str, ...] = ()

RUNNABLE_METRICS: tuple[str, ...] = ALL_METRICS + OPT_IN_METRICS
