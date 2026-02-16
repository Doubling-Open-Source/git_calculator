"""
SQLite schema and cycle-time queries that mirror the DevLake lake.
Used to validate cycle-time calculations against the in-memory Python implementation.
See docs/lake_schema_for_sqlite.md and lake_schema_gitextractor_refdiff.md.
"""

import sqlite3
from typing import List, Tuple, Optional, Any

from src.git_ir import git_log

# Default repo id when running from current repo (single-repo)
DEFAULT_REPO_ID = "local:git_calculator"

COMMITS_DDL = """
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT
);
"""

REFS_DDL = """
CREATE TABLE IF NOT EXISTS refs (
  repo_id TEXT
);
"""


def get_full_sha(commit) -> str:
    """Return full 40-char sha from a git_obj commit (str subclass may truncate __str__)."""
    return commit[:] if hasattr(commit, "__getitem__") else str(commit)


def create_db(path: Optional[str] = None) -> sqlite3.Connection:
    """Create an in-memory or file SQLite DB with commits (and optional refs) schema."""
    conn = sqlite3.connect(path or ":memory:")
    conn.executescript(COMMITS_DDL)
    conn.executescript(REFS_DDL)
    return conn


def populate_commits_from_log(
    conn: sqlite3.Connection,
    logs: Optional[List[Any]] = None,
    repo_id: str = DEFAULT_REPO_ID,
) -> int:
    """
    Populate commits table from git_log() (or provided logs). Returns row count.
    """
    if logs is None:
        logs = git_log()
    cur = conn.cursor()
    cur.execute("DELETE FROM commits WHERE _raw_data_params = ?", (repo_id,))
    for c in logs:
        sha = get_full_sha(c)
        author_email = c._author[0]
        committed_date = c._when
        cur.execute(
            "INSERT OR REPLACE INTO commits (sha, author_email, committed_date, _raw_data_params) VALUES (?, ?, ?, ?)",
            (sha, author_email, committed_date, repo_id),
        )
    conn.commit()
    return len(logs)


def _deltas_cte(repo_id: str) -> str:
    """SQL for deltas CTE: cycle_minutes per row (newer - older), ordered by committed_date."""
    return f"""
WITH ordered AS (
  SELECT sha, author_email, committed_date
  FROM commits
  WHERE _raw_data_params = ?
),
deltas AS (
  SELECT
    committed_date,
    author_email,
    ROUND((committed_date - LAG(committed_date) OVER (PARTITION BY author_email ORDER BY committed_date)) / 60.0, 2) AS cycle_minutes
  FROM ordered
)
SELECT committed_date, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
"""


def query_deltas(conn: sqlite3.Connection, repo_id: str = DEFAULT_REPO_ID) -> List[Tuple[int, float]]:
    """Return list of (committed_date_unix, cycle_minutes) matching Python calculate_time_deltas order (sorted by date)."""
    cur = conn.execute(_deltas_cte(repo_id).strip(), (repo_id,))
    rows = cur.fetchall()
    # Python uses (current_commit._when, delta_in_minutes); current_commit is the newer one
    return [(r[0], round(r[1], 2)) for r in rows]


def query_deltas_raw(conn: sqlite3.Connection, repo_id: str = DEFAULT_REPO_ID) -> List[Tuple[int, float]]:
    """Same as query_deltas but return raw rows for debugging (no rounding)."""
    cur = conn.execute(_deltas_cte(repo_id).strip(), (repo_id,))
    return [(r[0], r[1]) for r in cur.fetchall()]


def _fixed_bucket_stats_from_deltas(
    deltas: List[Tuple[int, float]], bucket_size: int
) -> List[Tuple[str, float, float, int, int]]:
    """
    Compute fixed-bucket stats (interval_start YYYY-MM, sum, average, p75, std) from deltas.
    Matches commit_statistics() logic; requires at least 2 deltas per bucket.
    """
    from datetime import datetime
    import numpy as np
    from statistics import stdev

    sorted_deltas = sorted(deltas, key=lambda x: x[0])
    result = []
    for i in range(0, len(sorted_deltas), bucket_size):
        sublist = sorted_deltas[i : i + bucket_size]
        if len(sublist) < 2:
            continue
        date = datetime.fromtimestamp(sublist[0][0])
        s_start_time = f"{date.year}-{date.month:02d}"
        minutes = [x[1] for x in sublist]
        s_sum = sum(minutes)
        s_average = round(s_sum / len(sublist), 2)
        s_p75 = int(round(np.percentile(minutes, 75), 0))
        s_std = int(round(stdev(minutes), 0))
        result.append((s_start_time, s_sum, s_average, s_p75, s_std))
    return result


def query_fixed_bucket_stats(
    conn: sqlite3.Connection,
    bucket_size: int,
    repo_id: str = DEFAULT_REPO_ID,
) -> List[Tuple[str, float, float, int, int]]:
    """
    Return fixed-bucket stats (interval_start, sum, average, p75, std) from SQLite deltas.
    Uses Python for p75/std to match commit_statistics() exactly (SQLite has no built-in).
    """
    deltas = query_deltas(conn, repo_id)
    return _fixed_bucket_stats_from_deltas(deltas, bucket_size)


def _by_month_stats_from_deltas(
    deltas: List[Tuple[int, float]]
) -> List[Tuple[str, float, float, int, int]]:
    """
    Compute by-month stats from deltas. Matches commit_statistics_normalized_by_month().
    """
    from datetime import datetime
    import numpy as np
    from statistics import stdev

    sorted_deltas = sorted(deltas, key=lambda x: x[0])
    month_buckets = []
    current_month = None
    for delta in sorted_deltas:
        date = datetime.fromtimestamp(delta[0])
        month_year = f"{date.year}-{date.month:02d}"
        if month_year != current_month:
            current_month = month_year
            month_buckets.append([current_month, []])
        month_buckets[-1][1].append(delta)
    result = []
    for m, sublist in month_buckets:
        if len(sublist) < 2:
            continue
        minutes = [x[1] for x in sublist]
        s_sum = sum(minutes)
        s_average = round(s_sum / len(sublist), 2)
        s_p75 = int(round(np.percentile(minutes, 75), 0))
        s_std = int(round(stdev(minutes), 0))
        result.append((m, s_sum, s_average, s_p75, s_std))
    return result


def query_by_month_stats(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
) -> List[Tuple[str, float, float, int, int]]:
    """Return by-month stats (month YYYY-MM, sum, average, p75, std) from SQLite deltas."""
    deltas = query_deltas(conn, repo_id)
    return _by_month_stats_from_deltas(deltas)
