"""Unit tests for schema_metrics.metrics_throughput_monthly."""

from __future__ import annotations

import time

from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_throughput_monthly import (
    CanonicalThroughputMonthly,
    compare_throughput_monthly,
    extract_throughput_monthly_select,
    throughput_monthly_canonical_from_logs,
    validate_throughput_monthly_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_contains_group_by_month():
    q = extract_throughput_monthly_select()
    assert ":repo_slug" in q
    assert "GROUP BY m.period_month" in q


def test_validate_two_authors_same_month():
    """Distinct author_count and commit_count must match SQL month bucket."""
    t0 = time.mktime((2024, 3, 10, 10, 0, 0, -1, -1, -1))
    t1 = time.mktime((2024, 3, 15, 10, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("a" * 40, t0, "alice@x"),
        FakeCommit("b" * 40, t1, "bob@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:tp", logs, batch)
    err = validate_throughput_monthly_for_logs(logs, "local:tp", conn=conn)
    assert err is None, err

    rows = throughput_monthly_canonical_from_logs(logs)
    assert len(rows) == 1
    assert rows[0].period_month == "2024-03"
    assert rows[0].commit_count == 2
    assert rows[0].distinct_author_count == 2


def test_legacy_month_key_normalizes_to_yyyy_mm():
    """Legacy throughput keys use YYYY-M; canonical rows use zero-padded months."""
    t = time.mktime((2024, 1, 5, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("c" * 40, t, "solo@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:tp2", logs, batch)
    err = validate_throughput_monthly_for_logs(logs, "local:tp2", conn=conn)
    assert err is None, err
    rows = throughput_monthly_canonical_from_logs(logs)
    assert rows[0].period_month == "2024-01"


def test_compare_detects_commit_count_mismatch():
    py = [CanonicalThroughputMonthly("2024-01", 5, 2)]
    sql = [CanonicalThroughputMonthly("2024-01", 4, 2)]
    assert compare_throughput_monthly(py, sql) is not None


def test_compare_detects_period_key_mismatch():
    py = [CanonicalThroughputMonthly("2024-01", 1, 1)]
    sql = [CanonicalThroughputMonthly("2024-02", 1, 1)]
    err = compare_throughput_monthly(py, sql)
    assert err is not None
    assert "only_py" in err or "only_sql" in err


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    """
    SQL scopes by repo_slug; Python aggregates logs. Populate as local:stored but
    validate as local:queried → empty SQL vs non-empty Python → mismatch (no mocks).
    """
    t0 = time.mktime((2024, 4, 1, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("s" * 40, t0, "u@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_throughput_monthly_for_logs(logs, "local:queried", conn=conn)
    assert err is not None
    assert "only_py" in err or "only_sql" in err
