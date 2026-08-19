"""Weekly SQL metrics vs legacy throughput_calculator across America/Los_Angeles DST."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_active_developers_weekly import (
    active_developers_weekly_canonical_from_logs,
    validate_active_developers_weekly_for_logs,
)
from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_throughput_per_active_developer_weekly import (
    throughput_per_active_developer_weekly_canonical_from_logs,
    validate_throughput_per_active_developer_weekly_for_logs,
)
from git_calculator.calculators.throughput_calculator import (
    calculate_active_developers_by_week,
    calculate_throughput_per_active_developer_by_week,
)
from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


@pytest.fixture
def america_los_angeles(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    if hasattr(time := __import__("time"), "tzset"):
        time.tzset()
    yield
    monkeypatch.delenv("TZ", raising=False)
    if hasattr(time, "tzset"):
        time.tzset()


def _spring_forward_dst_logs():
    """
    Commits where monday+7*86400 / monday-7*86400 disagree with timedelta lookbacks.

    Spring-forward 2020-W10 (Mon 2020-03-02): week_end via timedelta is 1h earlier
    than monday+604800. Lookback from W11 Mon via timedelta starts 1h later than
    monday-604800. Gap commits sit in those hours so broken fixed-day-second bounds
    would count different active-developer sets than legacy Python.
    """
    mon_w10 = datetime.fromisocalendar(2020, 10, 1)
    mon_w11 = datetime.fromisocalendar(2020, 11, 1)
    # After true W10 end (next Monday 00:00), still before monday_w10+7*86400.
    after_true_w10_end = int((mon_w10 + timedelta(days=7)).timestamp()) + 1
    # Before true W11 weeks_back=1 cutoff (W11 Mon - 1 week), after mon_w11-7*86400.
    before_true_lookback = int((mon_w11 - timedelta(weeks=1)).timestamp()) - 1800
    mid_w10 = int(mon_w10.timestamp()) + 3 * 86400
    mid_w11 = int(mon_w11.timestamp()) + 2 * 86400
    # Newest first (git_log order).
    return [
        FakeCommit("a" * 40, mid_w11, "in@x"),
        FakeCommit("b" * 40, after_true_w10_end, "gap_end@x"),
        FakeCommit("c" * 40, mid_w10, "in@x"),
        FakeCommit("d" * 40, before_true_lookback, "gap_start@x"),
    ]


def test_active_developers_weekly_dst_parity_vs_legacy(america_los_angeles):
    logs = _spring_forward_dst_logs()
    weeks_back = 1
    legacy = calculate_active_developers_by_week(logs, weeks_back=weeks_back)
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:dst-adw", logs, batch)

    err = validate_active_developers_weekly_for_logs(
        logs, "local:dst-adw", conn=conn, weeks_back=weeks_back
    )
    assert err is None, err

    rows = {
        r.period_week: r
        for r in active_developers_weekly_canonical_from_logs(logs, weeks_back=weeks_back)
    }
    assert set(rows) == set(legacy)
    for week, (commits, active_n, _emails) in legacy.items():
        assert rows[week].total_commits == commits
        assert rows[week].active_developer_count == active_n
        assert rows[week].weeks_back == weeks_back


def test_throughput_per_active_developer_weekly_dst_parity_vs_legacy(america_los_angeles):
    logs = _spring_forward_dst_logs()
    weeks_back = 1
    legacy = calculate_throughput_per_active_developer_by_week(logs, weeks_back=weeks_back)
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:dst-tpadw", logs, batch)

    err = validate_throughput_per_active_developer_weekly_for_logs(
        logs, "local:dst-tpadw", conn=conn, weeks_back=weeks_back
    )
    assert err is None, err

    rows = {
        r.period_week: r
        for r in throughput_per_active_developer_weekly_canonical_from_logs(
            logs, weeks_back=weeks_back
        )
    }
    assert set(rows) == set(legacy)
    for week, (commits, active_in_week, rate) in legacy.items():
        assert rows[week].total_commits == commits
        assert rows[week].active_authors_in_week == active_in_week
        assert rows[week].throughput_per_active_dev == pytest.approx(rate)
        assert rows[week].weeks_back == weeks_back
