"""Unit tests for schema_metrics.metrics_change_failure_monthly."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_change_failure_monthly import (
    CanonicalChangeFailureMonthly,
    compare_change_failure_monthly,
    extract_change_failure_monthly_select,
    validate_change_failure_monthly_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_references_metrics_subquery():
    q = extract_change_failure_monthly_select()
    assert ":repo_slug" in q
    assert "fix_like_commits" in q


def test_fix_keyword_in_body_matches_commits_export_flags():
    """SQL uses subject/body flags; batch must align subj/body with third %B field for Python path."""
    t1 = time.mktime((2024, 2, 1, 12, 0, 0, -1, -1, -1))
    t2 = time.mktime((2024, 2, 2, 12, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("0" * 40, t2, "a@x"),
        FakeCommit("1" * 40, t1, "a@x"),
    ]
    # subject+body drive flags in populate; third tuple = %B for validation keyword scan
    batch = {
        logs[0]._sha: ("noop", "", "noop"),
        logs[1]._sha: ("bugfix release", "", "bugfix release"),
    }
    conn = fresh_db_with_logs("local:cf", logs, batch)
    err = validate_change_failure_monthly_for_logs(
        logs, "local:cf", conn=conn, commit_messages=batch
    )
    assert err is None, err


def test_two_months_separate_buckets():
    t_jan = time.mktime((2024, 1, 15, 12, 0, 0, -1, -1, -1))
    t_feb = time.mktime((2024, 2, 10, 12, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("2" * 40, t_feb, "a@x"),
        FakeCommit("3" * 40, t_jan, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "x", "x")
    conn = fresh_db_with_logs("local:cf2", logs, batch)
    err = validate_change_failure_monthly_for_logs(
        logs, "local:cf2", conn=conn, commit_messages=batch
    )
    assert err is None, err


def test_compare_detects_rate_mismatch():
    py = [CanonicalChangeFailureMonthly("2024-01", 10, 2, 20.0)]
    sql = [CanonicalChangeFailureMonthly("2024-01", 10, 2, 50.0)]
    assert compare_change_failure_monthly(py, sql) is not None


def test_compare_detects_period_key_mismatch():
    py = [CanonicalChangeFailureMonthly("2024-01", 1, 0, 0.0)]
    sql = [CanonicalChangeFailureMonthly("2024-02", 1, 0, 0.0)]
    err = compare_change_failure_monthly(py, sql)
    assert err is not None
    assert "mismatch" in err or "py=" in err


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    t = time.mktime((2024, 8, 1, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("m" * 40, t, "a@x")]
    batch = message_batch_subject_body(logs, "noop", "noop")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_change_failure_monthly_for_logs(
        logs, "local:queried", conn=conn, commit_messages=batch
    )
    assert err is not None
    assert "period_month" in err or "py=" in err or "sql=" in err
