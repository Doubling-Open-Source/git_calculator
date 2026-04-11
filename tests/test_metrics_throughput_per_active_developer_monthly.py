"""Tests for ``metrics_throughput_per_active_developer_monthly`` (ADR 0007).

Validation matches ``calculate_throughput_per_active_developer``; SQL uses ``YYYY-MM`` keys.
"""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_throughput_per_active_developer_monthly import (
    CanonicalThroughputPerActiveDeveloperMonthly,
    compare_throughput_per_active_developer_monthly,
    extract_throughput_per_active_developer_monthly_select,
    validate_throughput_per_active_developer_monthly_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_uses_labeled_cte_and_portable_month_start():
    q = extract_throughput_per_active_developer_monthly_select()
    assert "WITH labeled AS (" in q
    assert "strftime" in q and "printf" in q and "'utc'" in q
    assert "month_start_unix" in q
    assert ":repo_slug" in q
    assert ":weeks_back" in q


def test_pre_month_activity_intersection_matches_canonical():
    """Author with May + June commits: June row has throughput 1/1 for weeks_back=4."""
    may = time.mktime((2024, 5, 20, 10, 0, 0, -1, -1, -1))
    june = time.mktime((2024, 6, 15, 12, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("a" * 40, june, "one@x"),
        FakeCommit("b" * 40, may, "one@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:tpadm", logs, batch)
    err = validate_throughput_per_active_developer_monthly_for_logs(
        logs, "local:tpadm", conn=conn, weeks_back=4
    )
    assert err is None, err


def test_june_only_commit_zero_denominator_when_no_pre_month_activity():
    """Solo June commit: no prior-window activity → active_authors_in_month 0."""
    june = time.mktime((2024, 6, 15, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("a" * 40, june, "solo@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:tpadm2", logs, batch)
    err = validate_throughput_per_active_developer_monthly_for_logs(
        logs, "local:tpadm2", conn=conn, weeks_back=4
    )
    assert err is None, err


def test_compare_detects_throughput_mismatch():
    k = ("2024-06", 4)
    py = [CanonicalThroughputPerActiveDeveloperMonthly(k[0], k[1], 2, 1, 2.0)]
    sql = [CanonicalThroughputPerActiveDeveloperMonthly(k[0], k[1], 2, 1, 99.0)]
    assert compare_throughput_per_active_developer_monthly(py, sql) is not None


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    t = time.mktime((2024, 7, 2, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("w" * 40, t, "z@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_throughput_per_active_developer_monthly_for_logs(
        logs, "local:queried", conn=conn
    )
    assert err is not None
    assert "mismatch" in err or "only_" in err.lower()
