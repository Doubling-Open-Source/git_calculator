"""
SQLite schema mirroring the DevLake lake.
Shared by cycle_time and change_failure sqlite_lake calculators.
See docs/lake_schema_for_sqlite.md.
"""

import sqlite3
from typing import List, Optional, Any

from src.git_ir import git_log
from src.util.git_util import git_run

DEFAULT_REPO_ID = "local:git_calculator"

# Mirrors DevLake lake.commits; committed_date as INTEGER (Unix) for LAG/diff.
COMMITS_DDL = """
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT,
  message TEXT
);
"""


def get_full_sha(commit) -> str:
    """Return full 40-char sha from a git_obj commit (str subclass may truncate __str__)."""
    return commit[:] if hasattr(commit, "__getitem__") else str(commit)


def create_db(path: Optional[str] = None) -> sqlite3.Connection:
    """Create an in-memory or file SQLite DB with commits schema."""
    conn = sqlite3.connect(path or ":memory:")
    conn.executescript(COMMITS_DDL)
    return conn


def populate_commits_from_log(
    conn: sqlite3.Connection,
    logs: Optional[List[Any]] = None,
) -> int:
    """
    Populate commits table from git_log() (or provided logs). Returns row count.
    """
    if logs is None:
        logs = git_log()
    cur = conn.cursor()
    cur.execute("DELETE FROM commits WHERE _raw_data_params = ?", (DEFAULT_REPO_ID,))
    for c in logs:
        sha = get_full_sha(c)
        author_email = c._author[0]
        committed_date = c._when
        try:
            msg = git_run("log", "-n", "1", "--format=%B", c).stdout.strip()
        except Exception:
            msg = ""
        cur.execute(
            "INSERT OR REPLACE INTO commits (sha, author_email, committed_date, _raw_data_params, message) VALUES (?, ?, ?, ?, ?)",
            (sha, author_email, committed_date, DEFAULT_REPO_ID, msg or None),
        )
    conn.commit()
    return len(logs)
