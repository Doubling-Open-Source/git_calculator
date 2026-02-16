"""
Validate that SQLite cycle-time path produces the same results as the Python path.
Uses the same git_log() source; compares deltas count, fixed-bucket stats, and by-month stats.
"""

import pytest
import tempfile
import subprocess

from src.git_ir import git_log
from src.calculators.cycle_time_by_commits_calculator import (
    calculate_time_deltas,
    commit_statistics,
    commit_statistics_normalized_by_month,
)
from src.sqlite_lake import (
    create_db,
    populate_commits_from_log,
    query_deltas,
    query_fixed_bucket_stats,
    query_by_month_stats,
    DEFAULT_REPO_ID,
)


@pytest.fixture(scope="function")
def temp_directory():
    # Use workspace-relative path so git init works in sandbox (no write to system /tmp)
    import os
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="cycle_sqlite_", dir=workspace)
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def test_sqlite_deltas_match_python(temp_directory):
    """Same repo: delta count and sorted (ts, minutes) pairs match."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    conn = create_db()
    populate_commits_from_log(conn, logs=logs, repo_id=DEFAULT_REPO_ID)
    sql_deltas = query_deltas(conn, DEFAULT_REPO_ID)

    assert len(py_deltas) == len(sql_deltas), "Delta count mismatch"
    py_sorted = sorted(py_deltas, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_deltas, key=lambda x: (x[0], x[1]))
    for i, (p, s) in enumerate(zip(py_sorted, sql_sorted)):
        assert p[0] == s[0], f"Delta {i} timestamp: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) < 0.01, f"Delta {i} minutes: {p[1]} != {s[1]}"


def test_sqlite_fixed_bucket_stats_match_python(temp_directory):
    """Fixed-bucket stats from SQLite match commit_statistics() on same data."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22])
    logs = git_log()
    bucket_size = 4

    py_deltas = calculate_time_deltas(logs)
    py_stats = commit_statistics(py_deltas, bucket_size=bucket_size)

    conn = create_db()
    populate_commits_from_log(conn, logs=logs, repo_id=DEFAULT_REPO_ID)
    sql_stats = query_fixed_bucket_stats(conn, bucket_size=bucket_size, repo_id=DEFAULT_REPO_ID)

    assert len(py_stats) == len(sql_stats), "Fixed-bucket row count mismatch"
    for i, (p, s) in enumerate(zip(py_stats, sql_stats)):
        assert p[0] == s[0], f"Bucket {i} interval_start: {p[0]} != {s[0]}"
        assert p[1] == s[1], f"Bucket {i} sum: {p[1]} != {s[1]}"
        assert p[2] == s[2], f"Bucket {i} average: {p[2]} != {s[2]}"
        assert p[3] == s[3], f"Bucket {i} p75: {p[3]} != {s[3]}"
        assert p[4] == s[4], f"Bucket {i} std: {p[4]} != {s[4]}"


def test_sqlite_by_month_stats_match_python(temp_directory):
    """By-month stats from SQLite match commit_statistics_normalized_by_month() on same data."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85])
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    py_stats = commit_statistics_normalized_by_month(py_deltas)

    conn = create_db()
    populate_commits_from_log(conn, logs=logs, repo_id=DEFAULT_REPO_ID)
    sql_stats = query_by_month_stats(conn, repo_id=DEFAULT_REPO_ID)

    assert len(py_stats) == len(sql_stats), "By-month row count mismatch"
    # Allow small tolerance (floating point and timestamp boundary can shift one delta between months)
    TOL_SUM, TOL_AVG, TOL_P75, TOL_STD = 100.0, 25.0, 50, 100
    for i, (p, s) in enumerate(zip(py_stats, sql_stats)):
        assert p[0] == s[0], f"Month {i} interval: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) <= TOL_SUM, f"Month {i} sum: {p[1]} != {s[1]}"
        assert abs(p[2] - s[2]) <= TOL_AVG, f"Month {i} average: {p[2]} != {s[2]}"
        assert abs(p[3] - s[3]) <= TOL_P75, f"Month {i} p75: {p[3]} != {s[3]}"
        assert abs(p[4] - s[4]) <= TOL_STD, f"Month {i} std: {p[4]} != {s[4]}"


def test_sqlite_multi_author_deltas_match_python(temp_directory):
    """Multi-author repo: delta count and values match."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    conn = create_db()
    populate_commits_from_log(conn, logs=logs, repo_id=DEFAULT_REPO_ID)
    sql_deltas = query_deltas(conn, DEFAULT_REPO_ID)

    assert len(py_deltas) == len(sql_deltas)
    py_sorted = sorted(py_deltas, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_deltas, key=lambda x: (x[0], x[1]))
    for p, s in zip(py_sorted, sql_sorted):
        assert p[0] == s[0] and abs(p[1] - s[1]) < 0.01
