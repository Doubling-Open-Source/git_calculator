"""Shared fake commits and helpers for schema_metrics unit tests (no git repo required)."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from src.calculators.sqlite_lake.commits_export_populate import (
    CommitMessagesBatch,
    create_commits_export_db,
    populate_commits_export_from_logs,
)


class FakeCommit:
    """git_log order (newest first); sliceable sha for get_full_sha."""

    __slots__ = ("_sha", "_when", "_author")

    def __init__(self, sha40: str, when: float, email: str) -> None:
        self._sha = sha40
        self._when = when
        self._author = (email,)

    def __getitem__(self, key):
        return self._sha[key]


def message_batch_subject_body(
    logs: List[FakeCommit], subject: str, body: str
) -> CommitMessagesBatch:
    """Third tuple element mirrors %B (used by change_failure validation path)."""
    t = (subject, body, body)
    return {c._sha: t for c in logs}


def populate_export(
    conn: Any,
    repo_slug: str,
    logs: List[FakeCommit],
    batch: Optional[CommitMessagesBatch],
) -> None:
    populate_commits_export_from_logs(conn, repo_slug, logs, commit_messages=batch)


def fresh_db_with_logs(
    repo_slug: str,
    logs: List[FakeCommit],
    batch: Optional[CommitMessagesBatch] = None,
):
    conn = create_commits_export_db()
    populate_export(conn, repo_slug, logs, batch)
    return conn


def apply_commit_parent_edges(
    conn: sqlite3.Connection,
    repo_slug: str,
    child_to_ordered_parents: Dict[str, List[str]],
) -> None:
    """
    Set ``parent_shas`` / ``parent_count`` on ``commits_export`` and mirror rows in
    ``commit_parent_edges`` (Git parent order: index 0 = first parent).
    """
    cur = conn.cursor()
    for child, plist in child_to_ordered_parents.items():
        n = len(plist)
        ps = " ".join(plist) if plist else ""
        cur.execute(
            """
            UPDATE commits_export
            SET parent_count = ?, parent_shas = ?
            WHERE repo_slug = ? AND sha = ?
            """,
            (n, ps, repo_slug, child),
        )
        cur.execute(
            "DELETE FROM commit_parent_edges WHERE repo_slug = ? AND child_sha = ?",
            (repo_slug, child),
        )
        for ord_i, p in enumerate(plist):
            cur.execute(
                """
                INSERT INTO commit_parent_edges (repo_slug, child_sha, parent_sha, parent_ord)
                VALUES (?, ?, ?, ?)
                """,
                (repo_slug, child, p, ord_i),
            )
    conn.commit()
