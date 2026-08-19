"""Operator-visible work-style: commit set and change-failure signal."""

import os
import subprocess
import sys
import tempfile
from datetime import datetime

import pytest

from git_calculator.calculators.change_failure_calculator import (
    calculate_change_failure_rate,
    extract_commit_data,
)
from git_calculator.calculators.sqlite_lake import SqliteLake
from git_calculator.calculators.sqlite_lake.schema_metrics.metrics_change_failure_monthly import (
    validate_change_failure_monthly_for_logs,
)
from git_calculator.git_ir import git_log
from git_calculator.util.git_util import get_repo_id, git_run
from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs


@pytest.fixture
def temp_directory():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    subprocess.run(["rm", "-rf", temp_dir], check=False)


def _commit(path, message, date):
    with open(path, "w") as f:
        f.write(message)
    git_run("add", path)
    formatted = date.strftime("%Y-%m-%dT%H:%M:%S")
    os.environ["GIT_COMMITTER_DATE"] = formatted
    os.environ["GIT_AUTHOR_DATE"] = formatted
    git_run(
        "commit",
        "-m",
        message,
        "--author",
        "Author 1 <author1@example.com>",
    )
    del os.environ["GIT_COMMITTER_DATE"]
    del os.environ["GIT_AUTHOR_DATE"]


def _squash_style_fixture(temp_directory):
    os.chdir(temp_directory)
    git_run("init", "-b", "main")
    when = datetime(2024, 6, 15, 12, 0, 0)
    _commit(
        "app.txt",
        "feat: login\n\nfix leftover from stacked commits",
        when,
    )
    git_run("checkout", "-b", "topic")
    _commit("topic.txt", "hotfix: only on topic", when)
    git_run("checkout", "main")


def test_squash_ignores_body_fix_keyword(temp_directory):
    _squash_style_fixture(temp_directory)
    logs = git_log(work_style="squash")
    rates = calculate_change_failure_rate(
        extract_commit_data(logs, work_style="squash")
    )
    assert rates["2024-06"] == 0


def test_all_branches_counts_body_fix_keyword(temp_directory):
    _squash_style_fixture(temp_directory)
    logs = git_log(work_style="all-branches")
    rates = calculate_change_failure_rate(
        extract_commit_data(logs, work_style="all-branches")
    )
    assert rates["2024-06"] > 0


def test_squash_hotfix_summary_is_fix_like(temp_directory):
    os.chdir(temp_directory)
    git_run("init", "-b", "main")
    _commit("a.txt", "hotfix: login", datetime(2024, 6, 15, 12, 0, 0))
    logs = git_log(work_style="squash")
    rates = calculate_change_failure_rate(
        extract_commit_data(logs, work_style="squash")
    )
    assert rates["2024-06"] == 100.0


def test_squash_omits_topic_only_commits(temp_directory):
    _squash_style_fixture(temp_directory)
    squash_logs = git_log(work_style="squash")
    all_logs = git_log(work_style="all-branches")
    assert len(squash_logs) == 1
    assert len(all_logs) >= 2


def test_unknown_work_style_cli_fails_closed():
    from git_calculator.cli import main

    with pytest.raises(SystemExit) as caught:
        sys.argv = ["git-calculator", "single", ".", "--work-style", "nope"]
        main()
    assert caught.value.code != 0


def test_schema_squash_parity_subject_only():
    t1 = datetime(2024, 2, 1, 12, 0, 0).timestamp()
    logs = [FakeCommit("a" * 40, t1, "a@x")]
    batch = {
        logs[0]._sha: (
            "feat: login",
            "fix leftover",
            "feat: login\n\nfix leftover",
        )
    }
    conn = fresh_db_with_logs("local:cf_squash", logs, batch)
    err = validate_change_failure_monthly_for_logs(
        logs,
        "local:cf_squash",
        conn=conn,
        commit_messages=batch,
        work_style="squash",
    )
    assert err is None, err


def test_lake_sql_squash_ignores_body(temp_directory):
    _squash_style_fixture(temp_directory)
    logs = git_log(work_style="squash")
    repo_id = get_repo_id()
    py_rates = calculate_change_failure_rate(
        extract_commit_data(logs, work_style="squash")
    )
    lake = SqliteLake()
    lake.load_logs(logs, repo_id)
    sql_list = lake.calculate_change_failure_rate_sql(
        repo_id=repo_id, work_style="squash"
    )
    py_list = sorted(py_rates.items())
    assert py_list == [(m, r) for m, r in sql_list]
