"""Unit tests for schema_metrics.metrics_cycle_time_monthly (boundaries, SQL parity)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import patch

from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_cycle_time_monthly import (
    CanonicalCycleTimeMonthly,
    commit_statistics_normalized_by_month_sql_localtime,
    compare_canonical_cycle_time_monthly,
    cycle_time_monthly_canonical_pair_for_logs,
    extract_cycle_time_monthly_materialization_select,
    read_metrics_cycle_time_monthly_sql,
    time_deltas_sql_aligned_minutes,
    validate_cycle_time_monthly_for_logs,
)
from git_calculator.util.git_util import CommitMessagesBatch

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_materialization_select_covers_metrics_sql():
    sql = read_metrics_cycle_time_monthly_sql()
    q = extract_cycle_time_monthly_materialization_select(sql)
    assert q.startswith("WITH ordered AS (")
    assert "ORDER BY b.month_year;" in q
    assert ":repo_slug" in q
    assert "log_ordinal" in q


def test_metrics_sql_monthly_matches_sql_aligned_python_path():
    """Validator uses metrics-local deltas + localtime months; legacy timedelta path may differ."""
    base = time.mktime((2024, 1, 1, 0, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("0" * 40, base + 1000.2, "a@x"),
        FakeCommit("1" * 40, base + 938.9, "a@x"),
        FakeCommit("2" * 40, base + 800.5, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:fake", logs, batch)

    err = validate_cycle_time_monthly_for_logs(
        logs, "local:fake", conn=conn, sum_avg_tol=0.0, p75_std_tol=0.0
    )
    assert err is None, err
    py_c, sql_c = cycle_time_monthly_canonical_pair_for_logs(logs, "local:fake", conn=conn)
    assert py_c == sql_c


def test_compare_flags_sum_minute_mismatch_at_zero_tol():
    a = [CanonicalCycleTimeMonthly("2024-01", 1.0, 1.0, 1, 1)]
    b = [CanonicalCycleTimeMonthly("2024-01", 100.0, 1.0, 1, 1)]
    err = compare_canonical_cycle_time_monthly(a, b, sum_avg_tol=0.0, p75_std_tol=0.0)
    assert err is not None
    assert "sum_minutes" in err or "Value mismatch" in err


def test_period_month_key_mismatch_surfaces_only_python_or_only_sql():
    py = [CanonicalCycleTimeMonthly("2024-01", 1.0, 1.0, 1, 1)]
    sql = [CanonicalCycleTimeMonthly("2024-02", 1.0, 1.0, 1, 1)]
    err = compare_canonical_cycle_time_monthly(py, sql, sum_avg_tol=0.0, p75_std_tol=0.0)
    assert err is not None
    assert "period_month" in err or "only" in err.lower()


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    """Materialization is per repo_slug; wrong slug → SQL rows missing months Python still has."""
    base = time.mktime((2024, 5, 1, 0, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("0" * 40, base + 200, "a@x"),
        FakeCommit("1" * 40, base + 100, "a@x"),
        FakeCommit("2" * 40, base + 0, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_cycle_time_monthly_for_logs(
        logs, "local:queried", conn=conn, sum_avg_tol=0.0, p75_std_tol=0.0
    )
    assert err is not None
    assert "period_month" in err or "only Python" in err or "only schema" in err


def _multi_day_logs_and_batch() -> tuple[list[FakeCommit], CommitMessagesBatch]:
    """Mirrors toy single-author offsets; git_log newest-first; messages for populate batch."""
    start = datetime(2023, 9, 1, 12, 0, 0)
    intervals = [10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85]
    email = "author1@example.com"
    by_creation: list[tuple[int, str, float]] = []
    for i, d in enumerate(intervals):
        file_index = i + 1
        t = (start + timedelta(days=d)).timestamp()
        sha = f"{i:040d}"
        by_creation.append((file_index, sha, t))
    by_creation_sorted = sorted(by_creation, key=lambda row: -intervals[row[0] - 1])
    logs = [FakeCommit(sha, t, email) for _, sha, t in by_creation_sorted]
    batch: CommitMessagesBatch = {}
    for file_index, sha, _ in by_creation:
        msg = f"Commit {file_index} by Author 1"
        if file_index % 4 == 0:
            msg += " - hotfix"
        elif file_index % 3 == 0:
            msg += " - bugfix"
        first = msg.split("\n", 1)[0].strip()
        batch[sha] = (first, "", msg)
    return logs, batch


def test_synthetic_git_log_end_to_end_matches_sql():
    logs, batch = _multi_day_logs_and_batch()
    repo_slug = "local:metrics_ctm_e2e"
    with patch(
        "git_calculator.calculators.sqlite_lake.commits_export_populate.git_log_commit_messages_batch",
        return_value=batch,
    ):
        err = validate_cycle_time_monthly_for_logs(logs, repo_slug)
    assert err is None, err


def test_p75_half_integer_bankers_matches_sql():
    """
    With n=3 samples, linear 75th percentile is the midpoint of the 2nd and 3rd
    smallest deltas (e.g. 2.5 from {0, 2, 3}). SQL uses the same half-to-even rule
    as Python ``int(round(..., 0))`` so validation passes at strict p75 tolerance.
    """
    base = time.mktime((2024, 6, 15, 12, 0, 0, -1, -1, -1))
    t = base
    # One author, newest-first: 0 min, 2 min, 3 min gaps → multiset {0, 2, 3}, p75 = 2.5 → 2
    logs = [
        FakeCommit("0" * 40, t, "a@x"),
        FakeCommit("1" * 40, t, "a@x"),
        FakeCommit("2" * 40, t - 120, "a@x"),
        FakeCommit("3" * 40, t - 300, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:p75_round_tie", logs, batch)

    err = validate_cycle_time_monthly_for_logs(
        logs,
        "local:p75_round_tie",
        conn=conn,
        sum_avg_tol=0.0,
        p75_std_tol=0.0,
    )
    assert err is None, err
