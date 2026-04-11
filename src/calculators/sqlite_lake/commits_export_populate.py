"""
Populate commits_export for validating schema/*.sql against Python calculators.

Uses the same commit ordering as git_log() iteration (see sqlite_lake parity notes).
Keyword flags follow ADR 0001 (%s / %b) for change-failure schema metrics.
"""

from __future__ import annotations

import sqlite3
from typing import Any, List, Optional

from src.calculators.sqlite_lake.commits_export_keywords import subject_body_keyword_flags
from src.calculators.sqlite_lake.paths import SCHEMA_DIR
from src.calculators.sqlite_lake.schema import get_full_sha
from src.util.git_util import git_log_commit_messages_batch, git_run

CommitMessagesBatch = dict[str, tuple[str, str, str]]

_COMMITS_EXPORT_SQL = SCHEMA_DIR / "commits_export.sql"


def commits_export_ddl_script() -> str:
    return _COMMITS_EXPORT_SQL.read_text(encoding="utf-8")


def create_commits_export_db(path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or ":memory:")
    conn.executescript(commits_export_ddl_script())
    return conn


def _git_subject_body(commit: Any) -> tuple[str, str]:
    subj = git_run("log", "-n", "1", "--format=%s", commit).stdout.strip()
    body = git_run("log", "-n", "1", "--format=%b", commit).stdout.strip()
    return subj, body


def populate_commits_export_from_logs(
    conn: sqlite3.Connection,
    repo_slug: str,
    logs: List[Any],
    *,
    commit_messages: Optional[CommitMessagesBatch] = None,
) -> int:
    """
    Replace rows for repo_slug with one row per commit.

    parent_count=0 and empty parent_shas; subject/body keyword flags from %s/%b.
    log_ordinal matches git_log() list order. If commit_messages is None, runs one
    batched git log for messages; pass a pre-built map to avoid duplicate git work.
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM commits_export WHERE repo_slug = ?", (repo_slug,))
    batch = commit_messages if commit_messages is not None else git_log_commit_messages_batch()
    for log_ordinal, c in enumerate(logs):
        sha = get_full_sha(c)
        author_ref = c._author[0]
        committed_at = int(c._when)
        got = batch.get(sha)
        if got is not None:
            subj, body, _raw_b = got
        else:
            subj, body = _git_subject_body(c)
        sk, bk = subject_body_keyword_flags(subj, body)
        cur.execute(
            """
            INSERT OR REPLACE INTO commits_export (
                repo_slug, sha, parent_shas, parent_count, committed_at, log_ordinal,
                committer_tz_offset, pii_protection_profile, author_ref, author_label_pii,
                subject_has_keywords, body_has_keywords,
                conventional_type, conventional_type_scope,
                schema_version, tenant_id
            ) VALUES (?, ?, '', 0, ?, ?, NULL, 'none', ?, NULL, ?, ?, NULL, NULL, 1, NULL)
            """,
            (repo_slug, sha, committed_at, log_ordinal, author_ref, sk, bk),
        )
    conn.commit()
    return len(logs)
