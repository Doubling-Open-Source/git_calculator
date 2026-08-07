"""End-to-end: ``validate_schema_metrics_for_logs`` with synthetic logs (no git repo; batch mocked)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from src.calculators.sqlite_lake.commits_export_populate import (
    create_commits_export_db,
    populate_commits_export_from_logs,
)
from src.calculators.sqlite_lake.schema_metrics import METRIC_ALL, validate_schema_metrics_for_logs
from src.calculators.sqlite_lake.schema_metrics.metrics_active_developers_monthly import (
    active_developers_monthly_canonical_from_logs,
)
from src.calculators.sqlite_lake.schema_metrics.metrics_cycle_time_monthly import (
    validate_cycle_time_monthly_for_logs,
)
from src.calculators.sqlite_lake.schema_metrics.metrics_throughput_monthly import (
    throughput_monthly_canonical_from_logs,
)
from src.util.git_util import CommitMessagesBatch

from tests.schema_metrics_fixtures import FakeCommit


def _single_author_toy_logs_and_batch() -> tuple[list[FakeCommit], CommitMessagesBatch]:
    """Same shape as ``ToyRepoCreator.create_custom_commits_single_author`` (day offsets from 2023-09-01)."""
    start = datetime(2023, 9, 1, 12, 0, 0)
    intervals = [10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85]
    email = "author1@example.com"
    by_creation: list[tuple[int, str, float]] = []
    for i, d in enumerate(intervals):
        file_index = i + 1
        t = (start + timedelta(days=d)).timestamp()
        sha = f"{i:040d}"
        by_creation.append((file_index, sha, t))
    # git_log order: newest commit first (largest day offset)
    by_creation_sorted = sorted(by_creation, key=lambda row: -intervals[row[0] - 1])
    logs = [FakeCommit(sha, t, email) for _, sha, t in by_creation_sorted]
    batch: CommitMessagesBatch = {}
    for file_index, sha, _ in by_creation:
        msg = f"Commit {file_index} by Author 1"
        if file_index % 4 == 0:
            msg += " - hotfix"
        elif file_index % 3 == 0:
            msg += " - bugfix"
        first = msg.split("\n", 1)[0].strip()
        batch[sha] = (first, "", msg)
    return logs, batch


def test_all_metrics_match_python_single_author_synthetic():
    """METRIC_ALL SQL↔legacy parity at tol=0; no synthetic parent-edge harness."""
    logs, batch = _single_author_toy_logs_and_batch()
    repo_slug = "local:schema_metrics_e2e"

    # External oracle: legacy helpers (not SQL write/read of the same rows).
    adm = active_developers_monthly_canonical_from_logs(logs)
    assert {r.period_month for r in adm} == {"2023-09", "2023-10", "2023-11"}
    assert all(r.unique_author_count == 1 for r in adm)
    tpm = throughput_monthly_canonical_from_logs(logs)
    assert sum(r.commit_count for r in tpm) == 12

    with patch(
        "src.calculators.sqlite_lake.schema_metrics.runner.git_log_commit_messages_batch",
        return_value=batch,
    ):
        err = validate_schema_metrics_for_logs(
            logs,
            repo_slug,
            METRIC_ALL,
            sum_avg_tol=0.0,
            p75_std_tol=0.0,
        )
    assert err is None, err


def test_cycle_time_monthly_fails_when_commits_export_repo_slug_not_validation_slug():
    """Populate under a phantom slug; validate with another slug → SQL empty vs Python not."""
    logs, batch = _single_author_toy_logs_and_batch()
    conn = create_commits_export_db()
    populate_commits_export_from_logs(
        conn, "phantom-repo-slug-not-used-for-query", logs, commit_messages=batch
    )
    err = validate_cycle_time_monthly_for_logs(
        logs, "local:real-slug-for-query", conn=conn, sum_avg_tol=0.0, p75_std_tol=0.0
    )
    assert err is not None
    assert "period_month" in err or "only Python" in err or "only schema" in err
