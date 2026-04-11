"""Shared fake commits and helpers for schema_metrics unit tests (no git repo required)."""

from __future__ import annotations

from typing import Any, List, Optional

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
