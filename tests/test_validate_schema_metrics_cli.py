"""Tests for ``scripts/validate_schema_metrics.py`` CLI (exit codes and wiring)."""

import importlib.util
import os
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

from src.util.toy_repo import ToyRepoCreator


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
            "src.calculators.sqlite_lake.schema_metrics.validate_schema_metrics_for_logs",
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


def test_cli_main_returns_zero_when_validator_ok(temp_directory):
    """Smoke: CLI exits 0 when the (possibly empty) metric pipeline reports OK."""
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
            "src.calculators.sqlite_lake.schema_metrics.validate_schema_metrics_for_logs",
            return_value=None,
        ) as m:
            spec = importlib.util.spec_from_file_location(
                "validate_schema_metrics_cli_ok", script
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert mod.main() == 0
        m.assert_called_once()
    finally:
        sys.argv = orig_argv
        os.chdir(orig_cwd)
