"""
Validate that SQL change-failure path produces the same results as the Python path.
Uses the same git_log() source; compares (month, rate) pairs.
"""

import pytest
import tempfile
import subprocess
import os

from src.git_ir import git_log
from src.calculators.change_failure_calculator import extract_commit_data, calculate_change_failure_rate
from src.calculators.sqlite_lake import (
    create_db,
    calculate_change_failure_rate_sql,
    DEFAULT_REPO_ID,
)


@pytest.fixture(scope="function")
def temp_directory():
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="change_failure_sqlite_", dir=workspace)
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def test_change_failure_rate_parity(temp_directory):
    """extract_commit_data + calculate_change_failure_rate (Python) vs calculate_change_failure_rate_sql return same (month, rate)."""
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits([7 * i for i in range(12)])  # weekly intervals, messages with bugfix/hotfix
    logs = git_log()

    data_by_month = extract_commit_data(logs)
    py_rates = calculate_change_failure_rate(data_by_month)
    py_list = sorted(py_rates.items())

    conn = create_db()
    sql_list = calculate_change_failure_rate_sql(conn, repo_id=DEFAULT_REPO_ID, logs=logs)

    assert len(py_list) == len(sql_list), "Month count mismatch"
    for i, ((m1, r1), (m2, r2)) in enumerate(zip(py_list, sql_list)):
        assert m1 == m2, f"Month {i}: {m1} != {m2}"
        assert abs(r1 - r2) < 0.01, f"Rate {i} ({m1}): Python {r1} vs SQL {r2}"
