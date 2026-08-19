"""Unit tests for schema_metrics.metrics_cycle_time_delta_events."""

from __future__ import annotations

import time

import pytest

from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_cycle_time_delta_events import (
    CanonicalCycleTimeDeltaEvent,
    DELTA_MINUTES_TOL,
    compare_cycle_time_delta_events,
    cycle_time_delta_events_canonical_from_logs,
    extract_cycle_time_delta_events_select,
    validate_cycle_time_delta_events_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_extract_select_filters_null_cycle_minutes():
    q = extract_cycle_time_delta_events_select()
    assert "WHERE d.cycle_minutes IS NOT NULL" in q
    assert "ORDER BY log_ordinal DESC" in q


def test_one_author_three_commits_yields_two_events_newest_first_order():
    """git_log order: index 0 newest; pairs (newest,older) and (older,oldest)."""
    base = 1_700_000_000
    logs = [
        FakeCommit("a" * 40, base + 2000, "solo@x"),
        FakeCommit("b" * 40, base + 1000, "solo@x"),
        FakeCommit("c" * 40, base + 0, "solo@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:de", logs, batch)
    err = validate_cycle_time_delta_events_for_logs(logs, "local:de", conn=conn)
    assert err is None, err

    ev = cycle_time_delta_events_canonical_from_logs(logs)
    assert len(ev) == 2
    assert ev[0].cycle_minutes == pytest.approx(1000 / 60.0, abs=0.01)
    assert ev[1].cycle_minutes == pytest.approx(1000 / 60.0, abs=0.01)


def test_two_authors_isolated_pairs_no_cross_author_edges():
    base = 1_700_000_000
    logs = [
        FakeCommit("0" * 40, base + 100, "a@x"),
        FakeCommit("1" * 40, base + 50, "a@x"),
        FakeCommit("2" * 40, base + 100, "b@x"),
        FakeCommit("3" * 40, base + 50, "b@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:de2", logs, batch)
    err = validate_cycle_time_delta_events_for_logs(logs, "local:de2", conn=conn)
    assert err is None, err
    ev = cycle_time_delta_events_canonical_from_logs(logs)
    assert len(ev) == 2
    authors = {e.author_ref for e in ev}
    assert authors == {"a@x", "b@x"}


def test_single_commit_per_author_zero_events():
    logs = [
        FakeCommit("z" * 40, 1_700_000_000, "only@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:de3", logs, batch)
    err = validate_cycle_time_delta_events_for_logs(logs, "local:de3", conn=conn)
    assert err is None, err
    assert cycle_time_delta_events_canonical_from_logs(logs) == []


def test_compare_minutes_within_tol_passes():
    a = CanonicalCycleTimeDeltaEvent("x", 100, "s1", 1.0, "s2")
    b = CanonicalCycleTimeDeltaEvent("x", 100, "s1", 1.0 + DELTA_MINUTES_TOL * 0.5, "s2")
    assert compare_cycle_time_delta_events([a], [b]) is None


def test_compare_minutes_beyond_tol_fails():
    a = CanonicalCycleTimeDeltaEvent("x", 100, "s1", 1.0, "s2")
    b = CanonicalCycleTimeDeltaEvent("x", 100, "s1", 10.0, "s2")
    assert compare_cycle_time_delta_events([a], [b]) is not None


def test_validate_fails_when_sql_repo_slug_not_in_commits_export():
    base = 1_710_000_000
    logs = [
        FakeCommit("0" * 40, base + 50, "p@x"),
        FakeCommit("1" * 40, base + 0, "p@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:stored", logs, batch)
    err = validate_cycle_time_delta_events_for_logs(logs, "local:queried", conn=conn)
    assert err is not None
    assert "delta_events" in err or "only_py" in err or "only_sql" in err
