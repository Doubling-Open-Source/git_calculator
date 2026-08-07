"""Unit tests for commits_export week bound helpers (DST-safe)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from src.calculators.sqlite_lake.commits_export_populate import period_week_and_monday_unix
from src.calculators.sqlite_lake.schema_metrics.metrics_active_developers_weekly import (
    extract_active_developers_weekly_select,
)
from src.calculators.sqlite_lake.schema_metrics.metrics_throughput_per_active_developer_weekly import (
    extract_throughput_per_active_developer_weekly_select,
)


@pytest.fixture
def america_los_angeles(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    # Force tzset so datetime.fromtimestamp / fromisocalendar see the new TZ.
    if hasattr(time := __import__("time"), "tzset"):
        time.tzset()
    yield
    # Restore for other tests in this process (best-effort).
    monkeypatch.delenv("TZ", raising=False)
    if hasattr(time, "tzset"):
        time.tzset()


def test_week_end_unix_matches_timedelta_across_dst(america_los_angeles):
    """Spring-forward week: next Monday via timedelta ≠ monday + 7*86400."""
    mon = datetime.fromisocalendar(2020, 10, 1)
    committed_at = int(mon.timestamp()) + 3600
    period_week, monday_unix, week_end_unix = period_week_and_monday_unix(committed_at)
    assert period_week == "2020-W10"
    assert monday_unix == int(mon.timestamp())
    expected_end = int((mon + timedelta(days=7)).timestamp())
    assert week_end_unix == expected_end
    assert week_end_unix - monday_unix != 7 * 86400


def test_weekly_sql_bounds_use_week_end_unix_not_fixed_day_seconds():
    for extract in (
        extract_active_developers_weekly_select,
        extract_throughput_per_active_developer_weekly_select,
    ):
        q = extract()
        assert "week_end_unix" in q
        assert "7 * 86400" not in q
        assert "7*86400" not in q
