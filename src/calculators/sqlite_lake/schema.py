"""
SQLite schema mirroring the DevLake lake.
Shared by cycle_time and change_failure sqlite_lake calculators.
See docs/lake_schema_for_sqlite.md.

``log_ordinal`` is a **local extension** (not in stock DevLake ``lake.commits``): 0-based
index in ``git_log()`` iteration order (newest first), so cycle-time SQL can match Python
and ``commits_export`` pairing via ``ORDER BY log_ordinal DESC``.
"""

import sqlite3
from typing import List, Optional, Any

from src.git_ir import git_log
from src.util.git_util import git_run

# Mirrors DevLake lake.commits + local log_ordinal for git_log-order cycle-time.
COMMITS_DDL = """
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT,
  message TEXT,
  log_ordinal INTEGER NOT NULL DEFAULT 0
);
"""


def get_full_sha(commit) -> str:
    """Return full 40-char sha from a git_obj commit (str subclass may truncate __str__)."""
    return commit[:] if hasattr(commit, "__getitem__") else str(commit)


def create_db(path: Optional[str] = None) -> sqlite3.Connection:
    """Create an in-memory or file SQLite DB with commits schema."""
    conn = sqlite3.connect(path or ":memory:")
    conn.executescript(COMMITS_DDL)
    _ensure_log_ordinal_column(conn)
    return conn


def _ensure_log_ordinal_column(conn: sqlite3.Connection) -> None:
    """Add log_ordinal to older on-disk DBs created before the local extension."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(commits)").fetchall()}
    if "log_ordinal" not in cols:
        conn.execute(
            "ALTER TABLE commits ADD COLUMN log_ordinal INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()


def get_first_repo_id(conn: sqlite3.Connection) -> Optional[str]:
    """Return the first (arbitrary) repo_id from commits, or None if empty. For default when caller omits repo_id."""
    row = conn.execute(
        "SELECT _raw_data_params FROM commits ORDER BY _raw_data_params LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def populate_commits_from_log(
    conn: sqlite3.Connection,
    repo_id: str,
    logs: Optional[List[Any]] = None,
) -> int:
    """
    Populate commits table from git_log() (or provided logs). Returns row count.

    ``log_ordinal`` matches list order (0 = newest), same contract as commits_export.
    Cycle-time SQL later does ``ORDER BY log_ordinal DESC`` so LAG walks oldest→newest.
    """
    if logs is None:
        logs = git_log()
    _ensure_log_ordinal_column(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM commits WHERE _raw_data_params = ?", (repo_id,))
    # enumerate order == git_log iteration order (newest first).
    for log_ordinal, c in enumerate(logs):
        sha = get_full_sha(c)
        author_email = c._author[0]
        committed_date = c._when
        try:
            msg = git_run("log", "-n", "1", "--format=%B", c).stdout.strip()
        except Exception:
            msg = ""
        cur.execute(
            """
            INSERT OR REPLACE INTO commits
              (sha, author_email, committed_date, _raw_data_params, message, log_ordinal)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sha, author_email, committed_date, repo_id, msg or None, log_ordinal),
        )
    conn.commit()
    return len(logs)
