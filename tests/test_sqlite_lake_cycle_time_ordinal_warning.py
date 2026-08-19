"""SqliteLake cycle-time: happy path uses log_ordinal; legacy path warns."""

from __future__ import annotations

import warnings

from git_calculator.calculators.sqlite_lake import SqliteLake
from git_calculator.calculators.sqlite_lake import cycle_time_by_commits_calculator as cycle
from tests.schema_metrics_fixtures import FakeCommit


def test_sqlite_lake_happy_path_uses_log_ordinal_without_warning():
    logs = [
        FakeCommit("a" * 40, 1_700_000_100, "a@x"),
        FakeCommit("b" * 40, 1_700_000_000, "a@x"),
    ]
    lake = SqliteLake()
    lake.load_logs(logs, "local:ord")
    row = lake.conn.execute(
        "SELECT log_ordinal FROM commits WHERE sha = ?", ("a" * 40,)
    ).fetchone()
    assert row[0] == 0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        deltas = lake.query_deltas(repo_id="local:ord")
    assert not any(issubclass(w.category, UserWarning) for w in caught)
    assert len(deltas) == 1
    assert "log_ordinal DESC" in cycle._deltas_cte()


def test_sqlite_lake_legacy_deltas_warn_no_log_ordinal(monkeypatch):
    monkeypatch.setattr(cycle, "_warned_lake_cycle_time_legacy_no_log_ordinal", False)
    logs = [
        FakeCommit("a" * 40, 1_700_000_100, "a@x"),
        FakeCommit("b" * 40, 1_700_000_000, "a@x"),
    ]
    lake = SqliteLake()
    lake.load_logs(logs, "local:legacy")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cycle.query_deltas_legacy_by_committed_date(lake.conn, "local:legacy")
        cycle.query_deltas_legacy_by_committed_date(lake.conn, "local:legacy")
    messages = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
    assert len(messages) == 1
    assert "log_ordinal" in messages[0]
    assert "backwards compatibility" in messages[0]
