"""Unit tests for schema_metrics.metrics_cycle_time_by_branches (ADR 0010)."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_cycle_time_by_branches import (
    CanonicalBranchLine,
    compare_branch_lines,
    extract_cycle_time_by_branches_select,
    validate_cycle_time_by_branches_for_logs,
)

from tests.schema_metrics_fixtures import (
    FakeCommit,
    apply_commit_parent_edges,
    fresh_db_with_logs,
    message_batch_subject_body,
)


def test_extract_select_reads_materialized_table():
    q = extract_cycle_time_by_branches_select()
    assert "metrics_cycle_time_by_branches" in q
    assert ":repo_slug" in q
    assert ":dataset_id" in q


def test_validate_matches_legacy_linear_top():
    """Linear history: Python BranchLine → table round-trip (not independent SQL)."""
    t0 = time.mktime((2024, 6, 3, 9, 0, 0, -1, -1, -1))
    t1 = time.mktime((2024, 6, 4, 9, 0, 0, -1, -1, -1))
    t2 = time.mktime((2024, 6, 5, 9, 0, 0, -1, -1, -1))
    c0 = "0" * 40
    c1 = "1" * 40
    c2 = "2" * 40
    # Newest first (git log order)
    logs = [
        FakeCommit(c2, t2, "a@x"),
        FakeCommit(c1, t1, "a@x"),
        FakeCommit(c0, t0, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:ctb", logs, batch)
    apply_commit_parent_edges(conn, "local:ctb", {c2: [c1], c1: [c0], c0: []})
    err = validate_cycle_time_by_branches_for_logs(
        logs, "local:ctb", conn=conn, strategy="top"
    )
    assert err is None, err


def test_compare_detects_strategy_mismatch():
    a = CanonicalBranchLine(
        branch_line_id="a",
        strategy="top",
        root_sha="0" * 40,
        merge_sha=None,
        departure_sha=None,
        commit_count=1,
        ramp_seconds=None,
        work_seconds=None,
        close_seconds=None,
        total_seconds=None,
    )
    b = CanonicalBranchLine(
        branch_line_id="a",
        strategy="reverse",
        root_sha="0" * 40,
        merge_sha=None,
        departure_sha=None,
        commit_count=1,
        ramp_seconds=None,
        work_seconds=None,
        close_seconds=None,
        total_seconds=None,
    )
    assert compare_branch_lines([a], [b]) is not None


def test_validate_errors_when_no_parent_edges():
    """Missing parent graph is not a silent success (no false SQL parity)."""
    t = time.mktime((2024, 7, 1, 12, 0, 0, -1, -1, -1))
    logs = [FakeCommit("a" * 40, t, "x@y")]
    conn = fresh_db_with_logs("local:noop", logs, message_batch_subject_body(logs, "s", ""))
    err = validate_cycle_time_by_branches_for_logs(logs, "local:noop", conn=conn)
    assert err is not None
    assert "commit_parent_edges" in err
