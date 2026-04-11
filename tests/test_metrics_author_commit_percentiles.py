"""Unit tests for schema_metrics.metrics_author_commit_percentiles (ADR 0009)."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_author_commit_percentiles import (
    CanonicalAuthorCommitPercentile,
    compare_author_commit_percentiles,
    extract_author_commit_percentiles_select,
    validate_author_commit_percentiles_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_uses_totals_and_as_of_period_all():
    q = extract_author_commit_percentiles_select()
    assert "WITH totals AS (" in q
    assert ":repo_slug" in q
    assert ":dataset_id" in q
    assert "'all'" in q or "AS as_of_period" in q
    assert "author_commit_percentile" in q


def test_validate_matches_legacy_two_authors():
    t0 = time.mktime((2024, 6, 3, 9, 0, 0, -1, -1, -1))
    t1 = time.mktime((2024, 6, 4, 9, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("a" * 40, t0, "alice@x"),
        FakeCommit("b" * 40, t0, "bob@x"),
        FakeCommit("c" * 40, t1, "alice@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:acp", logs, batch)
    err = validate_author_commit_percentiles_for_logs(logs, "local:acp", conn=conn)
    assert err is None, err


def test_validate_matches_legacy_tied_totals():
    """Two authors with same commit count get same max-rank percentile."""
    t = time.mktime((2024, 7, 1, 12, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("p" * 40, t, "p@x"),
        FakeCommit("q" * 40, t, "q@x"),
        FakeCommit("r" * 40, t, "r@x"),
        FakeCommit("s" * 40, t, "s@x"),
    ]
    # p and q: 1 each if grouped by legacy week? Same week same second - need same weekly bucket
    # Actually 4 commits same timestamp - extract_commits_by_author groups by week; all same week.
    # Consecutive same author merges: order sorted by time - all same time, order in list:
    # p, q, r, s each once -> 4 authors 1 commit each -> ties, all rank 4 -> 100%
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:tie", logs, batch)
    err = validate_author_commit_percentiles_for_logs(logs, "local:tie", conn=conn)
    assert err is None, err


def test_compare_detects_percentile_mismatch():
    k = "a@x"
    py = [CanonicalAuthorCommitPercentile(k, 2, 50.0)]
    sql = [CanonicalAuthorCommitPercentile(k, 2, 51.0)]
    assert compare_author_commit_percentiles(py, sql) is not None


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    t = time.mktime((2024, 8, 2, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("w" * 40, t, "z@x")]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_author_commit_percentiles_for_logs(logs, "local:queried", conn=conn)
    assert err is not None
