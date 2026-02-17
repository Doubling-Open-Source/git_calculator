"""
Base SQLite lake tests: schema, create_db, populate_commits_from_log.
Infrastructure tests shared by cycle_time and change_failure validation.
"""

import pytest
import tempfile
import subprocess
import os

from src.calculators.sqlite_lake import SqliteLake, create_db


@pytest.fixture(scope="function")
def temp_directory():
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="sqlite_lake_base_", dir=workspace)
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def test_create_db_returns_connection():
    conn = create_db()
    assert conn is not None
    conn.close()


def test_create_db_applies_schema():
    conn = create_db()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='commits'"
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "commits"
    conn.close()


def test_sqlite_lake_repo_id_format():
    """SqliteLake.repo_id is DevLake-style local:<name>."""
    lake = SqliteLake()
    assert lake.repo_id.startswith("local:")


def test_populate_commits_from_log_inserts_rows(temp_directory):
    from src.git_ir import git_log
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 3, 4, 5])
    logs = git_log()

    lake = SqliteLake()
    conn = create_db()
    count = lake.populate_commits_from_log(conn, logs=logs)
    cur = conn.execute("SELECT COUNT(*) FROM commits WHERE _raw_data_params = ?", (lake.repo_id,))
    db_count = cur.fetchone()[0]
    conn.close()

    assert count == len(logs)
    assert db_count == len(logs)


def test_populate_commits_from_log_replaces_on_same_repo(temp_directory):
    from src.git_ir import git_log
    from src.util.toy_repo import ToyRepoCreator

    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([1, 2, 3])
    logs = git_log()

    lake = SqliteLake()
    conn = create_db()
    lake.populate_commits_from_log(conn, logs=logs)
    lake.populate_commits_from_log(conn, logs=logs)
    cur = conn.execute("SELECT COUNT(*) FROM commits WHERE _raw_data_params = ?", (lake.repo_id,))
    count = cur.fetchone()[0]
    conn.close()

    assert count == len(logs)
