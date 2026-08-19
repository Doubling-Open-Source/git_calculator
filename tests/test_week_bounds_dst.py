"""Unit tests for commits_export week bound helpers (DST-safe)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from git_calculator.calculators.sqlite_lake.commits_export_populate import period_week_and_monday_unix


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
