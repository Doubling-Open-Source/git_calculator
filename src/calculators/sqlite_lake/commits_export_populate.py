"""
Populate commits_export for validating schema/*.sql against Python calculators.

Uses the same commit ordering as git_log() iteration (see sqlite_lake parity notes).
Keyword flags follow ADR 0001 (%s / %b) for change-failure schema metrics.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from subprocess import CalledProcessError, run as sp_run
from typing import Any, Dict, List, Optional, Tuple

from src.calculators.sqlite_lake.commits_export_keywords import subject_body_keyword_flags
from src.calculators.sqlite_lake.paths import SCHEMA_DIR
from src.calculators.sqlite_lake.schema import get_full_sha
from src.util.git_util import git_log_commit_messages_batch, git_run

CommitMessagesBatch = dict[str, tuple[str, str, str]]

_COMMITS_EXPORT_SQL = SCHEMA_DIR / "commits_export.sql"

# ``git rev-list --parents --no-walk`` per chunk (avoids 2×N subprocesses from per-SHA cat-file+log).
_REV_LIST_PARENTS_CHUNK = 512


def period_week_and_monday_unix(committed_at: int) -> Tuple[str, int, int]:
    """
    ISO week label, Monday 00:00 local (unix), and next Monday 00:00 local (unix).

    ``week_end_unix`` uses ``timedelta(days=7)`` like legacy weekly calculators — not
    ``monday + 7*86400`` (wrong across DST).
    """
    dt = datetime.fromtimestamp(int(committed_at))
    iso_y, iso_w, _ = dt.isocalendar()
    period_week = f"{iso_y}-W{iso_w:02d}"
    monday = datetime.fromisocalendar(iso_y, iso_w, 1)
    week_end = monday + timedelta(days=7)
    return period_week, int(monday.timestamp()), int(week_end.timestamp())


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
    # Parent edges FK → commits_export; clear edges first so re-populate works with FKs ON.
    cur.execute("DELETE FROM commit_parent_edges WHERE repo_slug = ?", (repo_slug,))
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
        period_week, week_monday_unix, week_end_unix = period_week_and_monday_unix(
            committed_at
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO commits_export (
                repo_slug, sha, parent_shas, parent_count, committed_at,
                period_week, week_monday_unix, week_end_unix, log_ordinal,
                committer_tz_offset, pii_protection_profile, author_ref, author_label_pii,
                subject_has_keywords, body_has_keywords,
                conventional_type, conventional_type_scope,
                schema_version, tenant_id
            ) VALUES (?, ?, '', 0, ?, ?, ?, ?, ?, NULL, 'none', ?, NULL, ?, ?, NULL, NULL, 3, NULL)
            """,
            (
                repo_slug,
                sha,
                committed_at,
                period_week,
                week_monday_unix,
                week_end_unix,
                log_ordinal,
                author_ref,
                sk,
                bk,
            ),
        )
    populate_commit_parent_edges_from_git_if_available(conn, repo_slug)
    conn.commit()
    return len(logs)


def _apply_parent_edges_for_sha(
    cur: sqlite3.Cursor,
    repo_slug: str,
    sha: str,
    parents: List[str],
) -> None:
    n = len(parents)
    ps = " ".join(parents)
    cur.execute(
        """
        UPDATE commits_export
        SET parent_count = ?, parent_shas = ?
        WHERE repo_slug = ? AND sha = ?
        """,
        (n, ps, repo_slug, sha),
    )
    cur.execute(
        "DELETE FROM commit_parent_edges WHERE repo_slug = ? AND child_sha = ?",
        (repo_slug, sha),
    )
    for i, p in enumerate(parents):
        cur.execute(
            """
            INSERT INTO commit_parent_edges (repo_slug, child_sha, parent_sha, parent_ord)
            VALUES (?, ?, ?, ?)
            """,
            (repo_slug, sha, p, i),
        )


def _parents_one_sha_slow_path(sha: str) -> Optional[List[str]]:
    """Return parent SHAs when ``sha`` exists in the repo as a commit; else None."""
    try:
        git_run("cat-file", "-e", sha + "^{commit}")
    except CalledProcessError:
        return None
    parents_s = git_run("log", "-1", "--format=%P", "--no-patch", sha).stdout.strip()
    return parents_s.split() if parents_s else []


def _parents_map_from_rev_list_batch(shas: List[str]) -> Optional[Dict[str, List[str]]]:
    """
    One ``git rev-list --parents --no-walk`` for many SHAs.
    Returns None if git failed (e.g. unknown object mixed into the batch).
    """
    if not shas:
        return {}
    cmd = ["git", "rev-list", "--parents", "--no-walk", *shas]
    proc = sp_run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        return None
    out: Dict[str, List[str]] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        commit = parts[0]
        out[commit] = parts[1:]
    return out


def _populate_parent_edges_chunk(
    cur: sqlite3.Cursor,
    repo_slug: str,
    shas: List[str],
) -> None:
    """Fill parent edges for ``shas`` using a batched rev-list when possible."""
    if not shas:
        return
    attempted = _parents_map_from_rev_list_batch(shas)
    if attempted is not None:
        for sha in shas:
            if sha in attempted:
                _apply_parent_edges_for_sha(cur, repo_slug, sha, attempted[sha])
        for sha in shas:
            if sha not in attempted:
                parents = _parents_one_sha_slow_path(sha)
                if parents is not None:
                    _apply_parent_edges_for_sha(cur, repo_slug, sha, parents)
        return

    if len(shas) == 1:
        parents = _parents_one_sha_slow_path(shas[0])
        if parents is not None:
            _apply_parent_edges_for_sha(cur, repo_slug, shas[0], parents)
        return

    mid = len(shas) // 2
    _populate_parent_edges_chunk(cur, repo_slug, shas[:mid])
    _populate_parent_edges_chunk(cur, repo_slug, shas[mid:])


def populate_commit_parent_edges_from_git_if_available(
    conn: sqlite3.Connection, repo_slug: str
) -> None:
    """
    When each export SHA exists as a commit object in the current Git repo, set
    ``parent_shas`` / ``parent_count`` and mirror ``commit_parent_edges``. No-op for
    synthetic SHAs (e.g. unit-test fixtures).

    Uses batched ``git rev-list --parents --no-walk`` (~N/512 subprocesses) with
    recursive fallback to the legacy per-SHA path when a batch fails.
    """
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT sha FROM commits_export WHERE repo_slug = ?", (repo_slug,)
    ).fetchall()
    all_shas = [r[0] for r in rows]
    for i in range(0, len(all_shas), _REV_LIST_PARENTS_CHUNK):
        chunk = all_shas[i : i + _REV_LIST_PARENTS_CHUNK]
        _populate_parent_edges_chunk(cur, repo_slug, chunk)
