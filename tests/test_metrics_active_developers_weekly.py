"""Unit tests for schema_metrics.metrics_active_developers_weekly."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_active_developers_weekly import (
    CanonicalActiveDevelopersWeekly,
    compare_active_developers_weekly,
    extract_active_developers_weekly_select,
    validate_active_developers_weekly_for_logs,
)
from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_uses_labeled_cte_and_iso_udf():
    q = extract_active_developers_weekly_select()
    assert "WITH labeled AS (" in q
    assert "c.period_week" in q
    assert "c.week_monday_unix" in q
    assert "MAX(week_monday_unix)" in q
    assert ":repo_slug" in q
    assert ":weeks_back" in q
    assert "COUNT(DISTINCT l.author_ref)" in q


def test_single_author_two_commits_same_week_matches_legacy():
    mon = time.mktime((2024, 6, 3, 9, 0, 0, -1, -1, -1))
    wed = time.mktime((2024, 6, 5, 15, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("n" * 40, wed, "one@x"),
        FakeCommit("o" * 40, mon, "one@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:adw", logs, batch)
    err = validate_active_developers_weekly_for_logs(logs, "local:adw", conn=conn)
    assert err is None, err


def test_compare_detects_count_mismatch():
    k = ("2024-W23", 4)
    py = [
        CanonicalActiveDevelopersWeekly(k[0], k[1], 2, 3),
    ]
    sql = [
        CanonicalActiveDevelopersWeekly(k[0], k[1], 2, 99),
    ]
    assert compare_active_developers_weekly(py, sql) is not None


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    t = time.mktime((2024, 7, 2, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("w" * 40, t, "z@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_active_developers_weekly_for_logs(
        logs, "local:queried", conn=conn
    )
    assert err is not None
    assert "mismatch" in err or "only_" in err.lower()
