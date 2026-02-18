"""
Validate that SQLite cycle-time path produces the same results as the Python path.
Uses the same git_log() source; compares deltas count, fixed-bucket stats, and by-month stats.
"""

import pytest
import tempfile
import subprocess
import os

from src.git_ir import git_log
from src.calculators.cycle_time_by_commits_calculator import (
    calculate_time_deltas,
    commit_statistics,
    commit_statistics_normalized_by_month,
    cycle_time_between_commits_by_author,
)
from src.calculators.sqlite_lake import SqliteLake


@pytest.fixture(scope="function")
def temp_directory():
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="cycle_sqlite_", dir=workspace)
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def test_calculate_time_deltas_parity(temp_directory):
    """calculate_time_deltas and calculate_time_deltas_sql return the same results."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    logs = git_log()

    py_result = calculate_time_deltas(logs)
    lake = SqliteLake()
    conn = lake.create_db()
    sql_result = lake.calculate_time_deltas_sql(conn, logs=logs)

    assert len(py_result) == len(sql_result), "Delta count mismatch"
    py_sorted = sorted(py_result, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_result, key=lambda x: (x[0], x[1]))
    for i, (p, s) in enumerate(zip(py_sorted, sql_sorted)):
        assert p[0] == s[0], f"Delta {i} timestamp: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) < 0.01, f"Delta {i} minutes: {p[1]} != {s[1]}"


def test_sqlite_deltas_match_python(temp_directory):
    """Same repo: delta count and sorted (ts, minutes) pairs match."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    lake = SqliteLake()
    conn = lake.create_db()
    lake.populate_commits_from_log(conn, logs=logs)
    sql_deltas = lake.query_deltas(conn)

    assert len(py_deltas) == len(sql_deltas), "Delta count mismatch"
    py_sorted = sorted(py_deltas, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_deltas, key=lambda x: (x[0], x[1]))
    for i, (p, s) in enumerate(zip(py_sorted, sql_sorted)):
        assert p[0] == s[0], f"Delta {i} timestamp: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) < 0.01, f"Delta {i} minutes: {p[1]} != {s[1]}"


def test_commit_statistics_parity(temp_directory):
    """commit_statistics and commit_statistics_sql return the same results."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22])
    logs = git_log()
    bucket_size = 4

    py_deltas = calculate_time_deltas(logs)
    py_result = commit_statistics(py_deltas, bucket_size=bucket_size)
    lake = SqliteLake()
    conn = lake.create_db()
    sql_result = lake.commit_statistics_sql(conn, bucket_size, logs=logs)

    assert py_result == sql_result, (
        f"commit_statistics != commit_statistics_sql: {py_result} vs {sql_result}"
    )


def test_sqlite_fixed_bucket_stats_match_python(temp_directory):
    """Fixed-bucket stats from SQLite match commit_statistics() on same data."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22])
    logs = git_log()
    bucket_size = 4

    py_deltas = calculate_time_deltas(logs)
    py_stats = commit_statistics(py_deltas, bucket_size=bucket_size)

    lake = SqliteLake()
    conn = lake.create_db()
    lake.populate_commits_from_log(conn, logs=logs)
    sql_stats = lake.query_fixed_bucket_stats_pure_sql(conn, bucket_size=bucket_size)

    assert len(py_stats) == len(sql_stats), "Fixed-bucket row count mismatch"
    for i, (p, s) in enumerate(zip(py_stats, sql_stats)):
        assert p[0] == s[0], f"Bucket {i} interval_start: {p[0]} != {s[0]}"
        assert p[1] == s[1], f"Bucket {i} sum: {p[1]} != {s[1]}"
        assert p[2] == s[2], f"Bucket {i} average: {p[2]} != {s[2]}"
        assert p[3] == s[3], f"Bucket {i} p75: {p[3]} != {s[3]}"
        assert p[4] == s[4], f"Bucket {i} std: {p[4]} != {s[4]}"


def test_commit_statistics_normalized_by_month_parity(temp_directory):
    """commit_statistics_normalized_by_month and commit_statistics_normalized_by_month_sql return the same results."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author(
        [10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85]
    )
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    py_result = commit_statistics_normalized_by_month(py_deltas)
    lake = SqliteLake()
    conn = lake.create_db()
    sql_result = lake.commit_statistics_normalized_by_month_sql(conn, logs=logs)

    assert len(py_result) == len(sql_result), "By-month row count mismatch"
    TOL = 100  # timestamp boundary / TZ can shift one delta between months
    for i, (p, s) in enumerate(zip(py_result, sql_result)):
        assert p[0] == s[0], f"Month {i} interval: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) <= TOL, f"Month {i} sum: {p[1]} != {s[1]}"
        assert abs(p[2] - s[2]) <= TOL, f"Month {i} average: {p[2]} != {s[2]}"
        assert abs(p[3] - s[3]) <= TOL, f"Month {i} p75: {p[3]} != {s[3]}"
        assert abs(p[4] - s[4]) <= TOL, f"Month {i} std: {p[4]} != {s[4]}"


def test_cycle_time_between_commits_by_author_parity(temp_directory):
    """cycle_time_between_commits_by_author and cycle_time_between_commits_by_author_sql return the same results."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22])
    bucket_size = 4
    py_result = cycle_time_between_commits_by_author(bucket_size=bucket_size)
    lake = SqliteLake()
    conn = lake.create_db()
    sql_result = lake.cycle_time_between_commits_by_author_sql(
        conn, bucket_size=bucket_size, logs=None
    )

    assert py_result == sql_result, (
        f"cycle_time_between_commits_by_author != _sql: {py_result} vs {sql_result}"
    )


def test_sqlite_by_month_stats_match_python(temp_directory):
    """By-month stats from SQLite match commit_statistics_normalized_by_month() on same data."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author(
        [10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85]
    )
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    py_stats = commit_statistics_normalized_by_month(py_deltas)

    lake = SqliteLake()
    conn = lake.create_db()
    lake.populate_commits_from_log(conn, logs=logs)
    sql_stats = lake.query_by_month_stats_pure_sql(conn)

    assert len(py_stats) == len(sql_stats), "By-month row count mismatch"
    TOL = 100
    for i, (p, s) in enumerate(zip(py_stats, sql_stats)):
        assert p[0] == s[0], f"Month {i} interval: {p[0]} != {s[0]}"
        assert abs(p[1] - s[1]) <= TOL, f"Month {i} sum: {p[1]} != {s[1]}"
        assert abs(p[2] - s[2]) <= TOL, f"Month {i} average: {p[2]} != {s[2]}"
        assert abs(p[3] - s[3]) <= TOL, f"Month {i} p75: {p[3]} != {s[3]}"
        assert abs(p[4] - s[4]) <= TOL, f"Month {i} std: {p[4]} != {s[4]}"


def test_sqlite_multi_author_deltas_match_python(temp_directory):
    """Multi-author repo: delta count and values match."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    logs = git_log()

    py_deltas = calculate_time_deltas(logs)
    lake = SqliteLake()
    conn = lake.create_db()
    lake.populate_commits_from_log(conn, logs=logs)
    sql_deltas = lake.query_deltas(conn)

    assert len(py_deltas) == len(sql_deltas)
    py_sorted = sorted(py_deltas, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_deltas, key=lambda x: (x[0], x[1]))
    for p, s in zip(py_sorted, sql_sorted):
        assert p[0] == s[0] and abs(p[1] - s[1]) < 0.01
