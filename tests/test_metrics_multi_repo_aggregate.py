"""Contract tests for ``schema_metrics.metrics_multi_repo_aggregate`` (ADR 0011)."""

from __future__ import annotations

import math
import os
import sqlite3
import tempfile

from src.calculators.multi_repo_calculator import MultiRepoCalculator
from src.multi_repo_manager import MultiRepoManager

from src.calculators.sqlite_lake.schema_metrics.metrics_multi_repo_aggregate import (
    materialize_metrics_multi_repo_aggregate,
    multi_repo_aggregate_materialization_rows,
    read_metrics_multi_repo_aggregate_rows,
    validate_multi_repo_aggregate_builtin_fixture,
    validate_multi_repo_aggregate_for_local_repo_paths,
    validate_multi_repo_aggregate_for_metrics_dict,
)
from src.util.toy_repo import ToyRepoCreator


def _minimal_two_repo_metrics() -> dict:
    """Deterministic fixture: two repos, one month / one ISO week overlap."""
    return {
        "repo_a": {
            "cycle_time_data": [("2024-01", 10.0, 2.0, 30.0, 4.0)],
            "failure_rate_data": [("2024-01", 0.2)],
            "active_dev_data": [
                ("2024-01", {"a1@x.com", "a2@x.com"}, 2),
            ],
            "throughput_data": [("2024-01", {"a1"}, 5)],
            "throughput_per_active_dev_data": [
                ("2024-W05", 100, 2, 50.0),
            ],
            "active_dev_weekly_data": [
                ("2024-W05", 100, 2, {"a1@x.com", "shared@x.com"}),
            ],
        },
        "repo_b": {
            "cycle_time_data": [("2024-01", 30.0, 4.0, 50.0, 6.0)],
            "failure_rate_data": [("2024-01", 0.4)],
            "active_dev_data": [
                ("2024-01", {"b1@x.com", "shared@x.com"}, 2),
            ],
            "throughput_data": [("2024-01", {"b1"}, 7)],
            "throughput_per_active_dev_data": [
                ("2024-W05", 50, 2, 25.0),
            ],
            "active_dev_weekly_data": [
                ("2024-W05", 50, 2, {"b1@x.com", "shared@x.com"}),
            ],
        },
    }


def test_multi_repo_calculator_reference_aggregates():
    m = _minimal_two_repo_metrics()
    calc = MultiRepoCalculator(MultiRepoManager())
    assert calc.aggregate_cycle_time_metrics(m) == [
        ("2024-01", 20.0, 3.0, 40.0, 5.0),
    ]
    fr = calc.aggregate_failure_rate_metrics(m)
    assert len(fr) == 1 and fr[0][0] == "2024-01" and math.isclose(fr[0][1], 0.3)
    # Union of author emails across repos for 2024-01: a1, a2, b1, shared = 4
    assert calc.aggregate_active_developers_metrics(m) == [("2024-01", 4)]
    assert calc.aggregate_throughput_metrics(m) == [("2024-01", 12)]
    # W05: total_commits 150, unique emails {a1, shared, b1} = 3 -> 150/3 = 50.0
    assert calc.aggregate_throughput_per_active_dev_metrics(m) == [("2024-W05", 50.0)]


def test_validate_multi_repo_aggregate_for_metrics_dict_ok():
    err, n_rows = validate_multi_repo_aggregate_for_metrics_dict(
        _minimal_two_repo_metrics(),
        batch_id="b1",
        cohort_id="c1",
        computed_at=1700000000,
    )
    assert err is None, err
    assert n_rows > 0


def test_materialize_and_round_trip_matches_expected_rows():
    m = _minimal_two_repo_metrics()
    batch_id, cohort_id = "b1", "c1"
    expected = multi_repo_aggregate_materialization_rows(
        m,
        batch_id,
        cohort_id,
        computed_at=1700000000,
    )

    conn = sqlite3.connect(":memory:")
    try:
        materialize_metrics_multi_repo_aggregate(conn, expected)
        got = read_metrics_multi_repo_aggregate_rows(conn, batch_id, cohort_id)
    finally:
        conn.close()

    assert len(got) == len(expected)
    assert got == expected


def test_builtin_fixture_validation_ok():
    assert validate_multi_repo_aggregate_builtin_fixture() is None


def test_validate_multi_repo_aggregate_for_local_repo_paths_two_git_repos():
    """``MultiRepoCalculator`` over two real toy repos, then aggregate parity."""
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    parent = tempfile.mkdtemp(prefix="mra_two_repos_", dir=workspace)
    try:
        d1 = os.path.join(parent, "a")
        d2 = os.path.join(parent, "b")
        os.makedirs(d1)
        os.makedirs(d2)
        ToyRepoCreator(d1).create_custom_commits_single_author([1, 2, 3])
        ToyRepoCreator(d2).create_custom_commits_single_author([4, 5, 6])
        err, _c, _v, n_rows = validate_multi_repo_aggregate_for_local_repo_paths(
            [d1, d2],
            computed_at=1700000000,
        )
        assert err is None, err
        assert n_rows > 0
    finally:
        import subprocess

        subprocess.run(["rm", "-rf", parent], check=False)
