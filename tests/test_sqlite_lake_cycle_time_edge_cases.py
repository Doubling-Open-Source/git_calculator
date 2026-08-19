"""
Edge cases surfaced by real-repo compare (a large sample git repo) that toy parity missed.

1. DST wall-clock: unix seconds/60 ≠ Python fromtimestamp timedelta across spring-forward.
2. Log order ≠ timestamp order: ORDER BY committed_date,sha pairs differently than git_log.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from git_calculator.calculators.cycle_time_by_commits_calculator import (
    calculate_time_deltas,
    commit_statistics,
)
from git_calculator.calculators.sqlite_lake import SqliteLake
from tests.schema_metrics_fixtures import FakeCommit


@pytest.fixture
def america_los_angeles(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    if hasattr(time := __import__("time"), "tzset"):
        time.tzset()
    yield
    monkeypatch.delenv("TZ", raising=False)
    if hasattr(time, "tzset"):
        time.tzset()


def _sorted_deltas(rows):
    return sorted((int(t), round(float(m), 2)) for t, m in rows)


def test_lake_deltas_match_python_across_spring_forward_dst(america_los_angeles):
    """
    Spring-forward 2020-03-08 (America/Los_Angeles): wall-clock gap is 1h shorter
    than raw unix/60. Happy-path SQL must use julianday(localtime), not epoch/60.
    """
    # Before and after the missing hour; same local clock time two calendar days apart
    # would be 48h wall / 47h unix across the spring-forward weekend — use a short span:
    before = int(datetime(2020, 3, 7, 12, 0, 0).timestamp())
    after = int(datetime(2020, 3, 9, 12, 0, 0).timestamp())
    unix_minutes = round((after - before) / 60.0, 2)
    wall = datetime.fromtimestamp(after) - datetime.fromtimestamp(before)
    wall_minutes = round(wall.days * 24 * 60 + wall.seconds / 60, 2)
    # Spring-forward: wall spans 48h on the clock, unix only 47h.
    assert wall_minutes - unix_minutes == 60.0  # fixture sanity: DST hour present

    # Newest first (git_log order).
    logs = [
        FakeCommit("a" * 40, after, "dev@x"),
        FakeCommit("b" * 40, before, "dev@x"),
    ]
    py = calculate_time_deltas(logs)
    assert len(py) == 1
    assert py[0][1] == wall_minutes
    assert py[0][1] != unix_minutes

    lake = SqliteLake()
    lake.load_logs(logs, "local:dst-edge")
    sql = lake.query_deltas(repo_id="local:dst-edge")
    assert _sorted_deltas(sql) == _sorted_deltas(py)


def test_lake_deltas_follow_git_log_order_not_timestamp_order(america_los_angeles):
    """
    Three commits whose timestamp order ≠ git_log order: committed_date,sha pairing
    yields a different multiset of deltas than Python calculate_time_deltas.
    """
    # Newest-first log: A@300, B@100, C@200.
    # Log adjacency: (A,B) and (B,C). Chronological LAG: B→C→A — different multisets.
    t_a, t_b, t_c = 1_700_000_300, 1_700_000_100, 1_700_000_200
    logs = [
        FakeCommit("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", t_a, "dev@x"),
        FakeCommit("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", t_b, "dev@x"),
        FakeCommit("cccccccccccccccccccccccccccccccccccccccc", t_c, "dev@x"),
    ]
    py = _sorted_deltas(calculate_time_deltas(logs))
    # Timestamp-ordered pairs (what lake did before log_ordinal): B→C (100s), C→A (100s).
    chrono_sorted = _sorted_deltas(
        [
            (t_c, round((t_c - t_b) / 60.0, 2)),
            (t_a, round((t_a - t_c) / 60.0, 2)),
        ]
    )
    assert py != chrono_sorted  # fixture sanity: log order ≠ time order

    lake = SqliteLake()
    lake.load_logs(logs, "local:ord-edge")
    sql = _sorted_deltas(lake.query_deltas(repo_id="local:ord-edge"))
    assert sql == py
    assert sql != chrono_sorted


def test_lake_fixed_bucket_matches_python_when_timestamps_tie(america_los_angeles):
    """
    Same child timestamps, different gap sizes: sha tie-break would put a different
    pair in the first bucket_size=2 window than Python's stable git_log emission order.
    """
    t_child = 1_700_200_000
    # Newest-first. Authors z then a then m (first-seen = log_ordinal order).
    # Child times all t_child; minutes 10, 30, 50 respectively.
    # Emission / stable-ts order: z(10), a(30), m(50).
    # Lexicographic sha order: a…, m…, z… → first bucket would be (30,50) not (10,30).
    logs = [
        FakeCommit("z" * 40, t_child, "z@x"),
        FakeCommit("a" * 40, t_child, "a@x"),
        FakeCommit("m" * 40, t_child, "m@x"),
        FakeCommit("z" * 39 + "0", t_child - 10 * 60, "z@x"),
        FakeCommit("a" * 39 + "0", t_child - 30 * 60, "a@x"),
        FakeCommit("m" * 39 + "0", t_child - 50 * 60, "m@x"),
    ]
    py_deltas = calculate_time_deltas(logs)
    assert len(py_deltas) == 3
    assert len({int(r[0]) for r in py_deltas}) == 1  # all same child timestamp

    py_stats = commit_statistics(py_deltas, bucket_size=2)
    assert len(py_stats) == 1
    # First bucket must be the two earliest in emission order (10 and 30), sum=40.
    assert abs(py_stats[0][1] - 40.0) < 0.02

    lake = SqliteLake()
    lake.load_logs(logs, "local:bucket-edge")
    sql_stats = lake.query_fixed_bucket_stats_pure_sql(2, repo_id="local:bucket-edge")
    assert len(sql_stats) == 1
    assert abs(sql_stats[0][1] - py_stats[0][1]) < 0.02
    assert abs(sql_stats[0][2] - py_stats[0][2]) < 0.02
