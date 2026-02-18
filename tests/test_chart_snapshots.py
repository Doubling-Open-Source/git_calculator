"""
Chart snapshot tests: Python vs SQL suites.
Uses toy repo with duplicate timestamps to exhibit Python/SQL differences.
Per docs/cycle_time_python_vs_sql_differences.md.
"""

import os
import subprocess
import tempfile

import pytest
from PIL import Image

from src.git_ir import git_log
from src.calculators import change_failure_calculator as cfc
from src.calculators import cycle_time_by_commits_calculator as cycle_calc
from src.calculators.sqlite_lake import SqliteLake
from src.util.toy_repo import ToyRepoCreator
from src.visualizers.chart_generator import plot_cycle_time, plot_change_failure_rate

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(os.path.join(SNAPSHOT_DIR, "python"), exist_ok=True)
os.makedirs(os.path.join(SNAPSHOT_DIR, "sql"), exist_ok=True)


@pytest.fixture(scope="function")
def snapshot_repo(tmp_path):
    """Create toy repo with duplicate timestamps. Restores cwd to workspace after test."""
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # Restore cwd in case a prior test left us in a deleted directory
    try:
        os.chdir(workspace)
    except OSError:
        pass
    temp_dir = str(tmp_path / "snapshot_repo")
    os.makedirs(temp_dir, exist_ok=True)
    try:
        trc = ToyRepoCreator(temp_dir)
        trc.create_commits_with_duplicate_timestamps()
        yield temp_dir
    finally:
        try:
            os.chdir(workspace)
        except OSError:
            pass


def test_cycle_time_snapshot_python(snapshot_repo, image_snapshot, tmp_path):
    """Python calc -> plot_cycle_time -> snapshot."""
    os.chdir(snapshot_repo)
    logs = git_log()
    tds = cycle_calc.calculate_time_deltas(logs)
    cycle_time_data = cycle_calc.commit_statistics_normalized_by_month(tds)
    output_file = str(tmp_path / "cycle_time.png")
    plot_cycle_time(cycle_time_data, output_path=output_file)
    img = Image.open(output_file)
    image_snapshot(img, os.path.join(SNAPSHOT_DIR, "python", "cycle_time.png"))


def test_cycle_time_snapshot_sql(snapshot_repo, image_snapshot, tmp_path):
    """SQL calc -> plot_cycle_time -> snapshot."""
    os.chdir(snapshot_repo)
    logs = git_log()
    lake = SqliteLake()
    conn = lake.create_db()
    try:
        cycle_time_data = lake.commit_statistics_normalized_by_month_sql(
            conn, logs=logs
        )
    finally:
        conn.close()
    output_file = str(tmp_path / "cycle_time.png")
    plot_cycle_time(cycle_time_data, output_path=output_file)
    img = Image.open(output_file)
    image_snapshot(img, os.path.join(SNAPSHOT_DIR, "sql", "cycle_time.png"))


def test_change_failure_rate_snapshot_python(snapshot_repo, image_snapshot, tmp_path):
    """Python calc -> plot_change_failure_rate -> snapshot."""
    os.chdir(snapshot_repo)
    logs = git_log()
    data_by_month = cfc.extract_commit_data(logs)
    failure_rate_data = [
        (month, rate)
        for month, rate in cfc.calculate_change_failure_rate(data_by_month).items()
    ]
    output_file = str(tmp_path / "change_failure_rate.png")
    plot_change_failure_rate(failure_rate_data, output_path=output_file)
    img = Image.open(output_file)
    image_snapshot(img, os.path.join(SNAPSHOT_DIR, "python", "change_failure_rate.png"))


def test_change_failure_rate_snapshot_sql(snapshot_repo, image_snapshot, tmp_path):
    """SQL calc -> plot_change_failure_rate -> snapshot."""
    os.chdir(snapshot_repo)
    logs = git_log()
    lake = SqliteLake()
    conn = lake.create_db()
    try:
        failure_rate_data = lake.calculate_change_failure_rate_sql(conn, logs=logs)
    finally:
        conn.close()
    output_file = str(tmp_path / "change_failure_rate.png")
    plot_change_failure_rate(failure_rate_data, output_path=output_file)
    img = Image.open(output_file)
    image_snapshot(img, os.path.join(SNAPSHOT_DIR, "sql", "change_failure_rate.png"))
