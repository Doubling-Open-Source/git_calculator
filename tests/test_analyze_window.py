"""Windowed SQL analyze: UTC window vs grain, lake messages, fail closed."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from git_calculator.util.git_util import git_run

FROM = datetime(2026, 6, 22, tzinfo=timezone.utc)
TO = datetime(2026, 8, 17, tzinfo=timezone.utc)


@pytest.fixture
def restore_cwd():
    cwd = os.getcwd()
    yield
    os.chdir(cwd)


def _init_repo(path: Path) -> None:
    os.chdir(path)
    git_run("init", "-b", "main")
    git_run("config", "user.email", "author1@example.com")
    git_run("config", "user.name", "Author 1")


def _commit(relpath: str, message: str, when: datetime) -> None:
    path = Path(relpath)
    path.write_text(message)
    git_run("add", str(path))
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
    os.environ["GIT_COMMITTER_DATE"] = stamp
    os.environ["GIT_AUTHOR_DATE"] = stamp
    git_run("commit", "-m", message, "--author", "Author 1 <author1@example.com>")
    del os.environ["GIT_COMMITTER_DATE"]
    del os.environ["GIT_AUTHOR_DATE"]


def _windowed_repo(tmp_path: Path, restore_cwd) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _commit("outside.txt", "fix: too early", datetime(2026, 5, 1, 12, tzinfo=timezone.utc))
    _commit(
        "app.txt",
        "fix(scope): login",
        datetime(2026, 6, 24, 12, tzinfo=timezone.utc),
    )
    return repo


def test_squash_fix_scope_counts_under_sql_window(tmp_path, restore_cwd):
    from git_calculator.analyze_window import analyze_window

    repo = _windowed_repo(tmp_path, restore_cwd)
    series = analyze_window(
        str(repo),
        window_start=FROM,
        window_end=TO,
        grain="weekly",
        backend="sql",
        work_style="squash",
    )
    assert sum(row["fix_commits"] for row in series) >= 1


def test_squash_ignores_body_only_fix_all_branches_counts_it(tmp_path, restore_cwd):
    from git_calculator.analyze_window import analyze_window

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _commit(
        "app.txt",
        "feat: login\n\nfix leftover from stacked commits",
        datetime(2026, 6, 24, 12, tzinfo=timezone.utc),
    )
    kwargs = dict(
        repo_path=str(repo),
        window_start=FROM,
        window_end=TO,
        grain="weekly",
        backend="sql",
    )
    squash = analyze_window(**kwargs, work_style="squash")
    all_branches = analyze_window(**kwargs, work_style="all-branches")
    assert sum(row["fix_commits"] for row in squash) == 0
    assert sum(row["fix_commits"] for row in all_branches) >= 1


def test_commits_outside_window_do_not_appear(tmp_path, restore_cwd):
    from git_calculator.analyze_window import analyze_window

    repo = _windowed_repo(tmp_path, restore_cwd)
    series = analyze_window(
        str(repo),
        window_start=FROM,
        window_end=TO,
        grain="weekly",
        backend="sql",
        work_style="squash",
    )
    assert sum(row["commits"] for row in series) == 1


def test_weekly_vs_monthly_row_keys(tmp_path, restore_cwd):
    from git_calculator.analyze_window import analyze_window

    repo = _windowed_repo(tmp_path, restore_cwd)
    kwargs = dict(
        repo_path=str(repo),
        window_start=FROM,
        window_end=TO,
        backend="sql",
        work_style="squash",
    )
    weekly = analyze_window(**kwargs, grain="weekly")
    monthly = analyze_window(**kwargs, grain="monthly")
    assert any("-W" in row["period"] for row in weekly)
    assert any(row["period"] == "2026-06" for row in monthly)
    assert not any("-W" in row["period"] for row in monthly)


def test_quiet_period_does_not_invent_a_change_failure_rate(tmp_path, restore_cwd):
    from git_calculator.analyze_window import analyze_window

    repo = _windowed_repo(tmp_path, restore_cwd)
    series = analyze_window(
        str(repo),
        window_start=FROM,
        window_end=TO,
        grain="weekly",
        backend="sql",
        work_style="squash",
    )
    quiet = next(row for row in series if row["commits"] == 0)
    assert quiet["change_failure_rate_pct"] is None


def _run_cli(argv: list[str]) -> int:
    from git_calculator.cli import main

    orig = sys.argv[:]
    try:
        sys.argv = argv
        try:
            main()
        except SystemExit as caught:
            return int(caught.code or 0)
        return 0
    finally:
        sys.argv = orig


def test_from_without_to_fails_closed():
    assert _run_cli(
        ["git-calculator", "single", ".", "--from", "2026-06-22T00:00:00Z"]
    ) != 0


def test_unknown_grain_fails_closed():
    assert _run_cli(["git-calculator", "single", ".", "--grain", "hourly"]) != 0


def test_python_backend_with_window_fails_closed():
    assert (
        _run_cli(
            [
                "git-calculator",
                "single",
                ".",
                "--from",
                "2026-06-22T00:00:00Z",
                "--to",
                "2026-08-17T00:00:00Z",
                "--backend",
                "python",
            ]
        )
        != 0
    )


def test_weekly_grain_without_window_fails_closed():
    assert _run_cli(["git-calculator", "single", ".", "--grain", "weekly"]) != 0
