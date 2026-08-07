"""Tests for commits_export populate (FK / re-populate behavior)."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.commits_export_populate import (
    create_commits_export_db,
    populate_commits_export_from_logs,
)
from tests.schema_metrics_fixtures import FakeCommit, apply_commit_parent_edges, message_batch_subject_body


def test_repopulate_with_foreign_keys_and_parent_edges_succeeds():
    """Second populate must clear parent edges before deleting commits_export rows."""
    repo = "local:fk_repop"
    t0 = time.mktime((2024, 6, 1, 12, 0, 0, 0, 0, -1))
    c0 = FakeCommit("a" * 40, t0, "a@ex.com")
    c1 = FakeCommit("b" * 40, t0 + 86400, "a@ex.com")
    logs = [c1, c0]
    batch = message_batch_subject_body(logs, "msg", "")

    conn = create_commits_export_db()
    conn.execute("PRAGMA foreign_keys = ON")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    populate_commits_export_from_logs(conn, repo, logs, commit_messages=batch)
    apply_commit_parent_edges(conn, repo, {c1._sha: [c0._sha], c0._sha: []})
    edge_n = conn.execute(
        "SELECT COUNT(*) FROM commit_parent_edges WHERE repo_slug = ?", (repo,)
    ).fetchone()[0]
    assert edge_n >= 1

    # Must not raise IntegrityError / OperationalError under FK enforcement.
    n = populate_commits_export_from_logs(conn, repo, logs, commit_messages=batch)
    assert n == 2
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM commits_export WHERE repo_slug = ?", (repo,)
        ).fetchone()[0]
        == 2
    )
