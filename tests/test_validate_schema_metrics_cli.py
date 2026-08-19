"""Tests for ``scripts/validate_schema_metrics.py`` CLI (exit codes and wiring)."""

import importlib.util
import os
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

from git_calculator.util.toy_repo import ToyRepoCreator


@pytest.fixture(scope="function")
def temp_directory():
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="validate_schema_metrics_cli_", dir=workspace)
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def test_cli_main_returns_one_when_validator_reports_error(temp_directory):
    """In-process: main() returns 1 if validate_schema_metrics_for_logs returns an error string."""
    trc = ToyRepoCreator(temp_directory)
    trc.create_custom_commits_single_author([10, 11, 12])
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script = os.path.join(repo_root, "scripts", "validate_schema_metrics.py")
    orig_cwd = os.getcwd()
    orig_argv = sys.argv[:]
    try:
        os.chdir(temp_directory)
        sys.argv = [
            "validate_schema_metrics.py",
            "--quiet",
            "--no-detail-log",
            "--repo-dir",
            temp_directory,
        ]
        with mock.patch(
            "git_calculator.calculators.sqlite_lake.schema_metrics.validate_schema_metrics_for_logs",
            return_value="[cycle_time_monthly]\nsynthetic mismatch",
        ):
            spec = importlib.util.spec_from_file_location(
                "validate_schema_metrics_cli", script
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert mod.main() == 1
    finally:
        sys.argv = orig_argv
        os.chdir(orig_cwd)


def test_cli_multi_repo_aggregate_passes_multiple_repo_dir_flags(temp_directory):
    """``--repo-dir`` may be repeated; paths are forwarded in order to the aggregate validator."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(repo_root)
    d1 = tempfile.mkdtemp(prefix="cli_mra_1_", dir=temp_directory)
    d2 = tempfile.mkdtemp(prefix="cli_mra_2_", dir=temp_directory)
    script = os.path.join(repo_root, "scripts", "validate_schema_metrics.py")
    orig_cwd = os.getcwd()
    orig_argv = sys.argv[:]
    try:
        os.chdir(repo_root)
        sys.argv = [
            "validate_schema_metrics.py",
            "--quiet",
            "--no-detail-log",
            "--metric",
            "multi_repo_aggregate",
            "--repo-dir",
            d1,
            "--repo-dir",
            d2,
        ]
        with mock.patch(
            "git_calculator.calculators.sqlite_lake.schema_metrics.validate_multi_repo_aggregate_for_local_repo_paths",
            return_value=(None, 0.0, 0.0, 0),
        ) as m:
            spec = importlib.util.spec_from_file_location(
                "validate_schema_metrics_cli_multi", script
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert mod.main() == 0
        m.assert_called_once()
        passed = m.call_args[0][0]
        assert passed == [os.path.abspath(d1), os.path.abspath(d2)]
    finally:
        sys.argv = orig_argv
        os.chdir(orig_cwd)
