"""
SQLite schema and cycle-time queries that mirror the DevLake lake.
All data-producing logic is in pure SQL (no numpy/Python for aggregates) so the same
queries can be used in Grafana/MySQL. Validation tests assert SQL matches Python.
See docs/lake_schema_for_sqlite.md and lake_schema_gitextractor_refdiff.md.
"""

import sqlite3
from typing import List, Tuple, Optional, Any

from src.git_ir import git_log
from src.util.git_util import git_run

# Default repo id when running from current repo (single-repo)
DEFAULT_REPO_ID = "local:git_calculator"

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
        try:
            msg = git_run("log", "-n", "1", "--format=%B", c).stdout.strip()
        except Exception:
            msg = ""
        cur.execute(
            "INSERT OR REPLACE INTO commits (sha, author_email, committed_date, _raw_data_params, message) VALUES (?, ?, ?, ?, ?)",
            (sha, author_email, committed_date, repo_id, msg or None),
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
    ROUND((committed_date - LAG(committed_date) OVER (PARTITION BY author_email ORDER BY committed_date, sha)) / 60.0, 2) AS cycle_minutes
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


# --- Pure SQL: fixed-bucket stats (commit_statistics equivalent) ---
# p75: numpy-style linear interpolation. index = (n-1)*0.75; p75 = (1-frac)*v_lo + frac*v_hi.
# stdev: sample stdev = SQRT(SUM((x-mean)^2)/(n-1)); computed via SUM(x^2)-n*mean^2.

def _sql_fixed_bucket_stats(repo_id: str, bucket_size: int) -> str:
    return f"""
WITH ordered AS (
  SELECT sha, author_email, committed_date FROM commits WHERE _raw_data_params = ?
),
deltas AS (
  SELECT committed_date, sha,
    ROUND((committed_date - LAG(committed_date) OVER (PARTITION BY author_email ORDER BY committed_date, sha)) / 60.0, 2) AS cycle_minutes
  FROM ordered
),
valid AS (
  SELECT committed_date, sha, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
),
numbered AS (
  SELECT committed_date, cycle_minutes,
    (ROW_NUMBER() OVER (ORDER BY committed_date, sha) - 1) / ? AS bucket_id,
    ROW_NUMBER() OVER (ORDER BY committed_date, sha) AS rn_global
  FROM valid
),
bucket_meta AS (
  SELECT bucket_id,
    MIN(committed_date) AS first_ts,
    SUM(cycle_minutes) AS s,
    SUM(cycle_minutes * cycle_minutes) AS s2,
    COUNT(*) AS n,
    CAST((COUNT(*) - 1) * 0.75 AS INT) + 1 AS k_lo,
    (COUNT(*) - 1) * 0.75 - CAST((COUNT(*) - 1) * 0.75 AS INT) AS frac
  FROM numbered
  GROUP BY bucket_id
  HAVING COUNT(*) >= 2
),
ranked AS (
  SELECT n.bucket_id, n.committed_date, n.cycle_minutes,
    ROW_NUMBER() OVER (PARTITION BY n.bucket_id ORDER BY n.cycle_minutes) AS rn
  FROM numbered n
  JOIN bucket_meta b ON n.bucket_id = b.bucket_id
),
p75_vals AS (
  SELECT b.bucket_id,
    MAX(CASE WHEN r.rn = b.k_lo THEN r.cycle_minutes END) AS v_lo,
    MAX(CASE WHEN r.rn = b.k_lo + 1 THEN r.cycle_minutes END) AS v_hi,
    b.frac
  FROM bucket_meta b
  LEFT JOIN ranked r ON r.bucket_id = b.bucket_id AND r.rn IN (b.k_lo, b.k_lo + 1)
  GROUP BY b.bucket_id, b.frac
)
SELECT
  strftime('%Y-%m', b.first_ts, 'unixepoch', 'localtime') AS interval_start,
  b.s AS s_sum,
  ROUND(b.s / b.n, 2) AS s_average,
  CAST(ROUND((1.0 - p.frac) * p.v_lo + p.frac * COALESCE(p.v_hi, p.v_lo), 0) AS INT) AS s_p75,
  CAST(ROUND(SQRT(MAX(0, (b.s2 - b.s * b.s * 1.0 / b.n) / (b.n - 1))), 0) AS INT) AS s_std
FROM bucket_meta b
JOIN p75_vals p ON p.bucket_id = b.bucket_id
ORDER BY b.bucket_id
"""


def query_fixed_bucket_stats_pure_sql(
    conn: sqlite3.Connection,
    bucket_size: int,
    repo_id: str = DEFAULT_REPO_ID,
) -> List[Tuple[str, float, float, int, int]]:
    """
    Fixed-bucket stats using only SQL (no numpy/Python). Matches commit_statistics().
    interval_start YYYY-MM, sum, average, p75 (linear interp), sample stdev.
    """
    sql = _sql_fixed_bucket_stats(repo_id, bucket_size).strip()
    cur = conn.execute(sql, (repo_id, bucket_size))
    return [tuple(r) for r in cur.fetchall()]


# --- Pure SQL: by-month stats (commit_statistics_normalized_by_month equivalent) ---

def _sql_by_month_stats(repo_id: str) -> str:
    return """
WITH ordered AS (
  SELECT sha, author_email, committed_date FROM commits WHERE _raw_data_params = ?
),
deltas AS (
  SELECT committed_date,
    ROUND((committed_date - LAG(committed_date) OVER (PARTITION BY author_email ORDER BY committed_date, sha)) / 60.0, 2) AS cycle_minutes
  FROM ordered
),
valid AS (
  SELECT committed_date, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
),
with_month AS (
  SELECT committed_date, cycle_minutes,
    strftime('%Y-%m', committed_date, 'unixepoch', 'localtime') AS month_year
  FROM valid
),
bucket_meta AS (
  SELECT month_year,
    SUM(cycle_minutes) AS s,
    SUM(cycle_minutes * cycle_minutes) AS s2,
    COUNT(*) AS n,
    CAST((COUNT(*) - 1) * 0.75 AS INT) + 1 AS k_lo,
    (COUNT(*) - 1) * 0.75 - CAST((COUNT(*) - 1) * 0.75 AS INT) AS frac
  FROM with_month
  GROUP BY month_year
  HAVING COUNT(*) >= 2
),
ranked AS (
  SELECT w.month_year, w.cycle_minutes,
    ROW_NUMBER() OVER (PARTITION BY w.month_year ORDER BY w.cycle_minutes) AS rn
  FROM with_month w
  JOIN bucket_meta b ON w.month_year = b.month_year
),
p75_vals AS (
  SELECT b.month_year,
    MAX(CASE WHEN r.rn = b.k_lo THEN r.cycle_minutes END) AS v_lo,
    MAX(CASE WHEN r.rn = b.k_lo + 1 THEN r.cycle_minutes END) AS v_hi,
    b.frac
  FROM bucket_meta b
  LEFT JOIN ranked r ON r.month_year = b.month_year AND r.rn IN (b.k_lo, b.k_lo + 1)
  GROUP BY b.month_year, b.frac
)
SELECT
  b.month_year AS interval_start,
  b.s AS s_sum,
  ROUND(b.s / b.n, 2) AS s_average,
  CAST(ROUND((1.0 - p.frac) * p.v_lo + p.frac * COALESCE(p.v_hi, p.v_lo), 0) AS INT) AS s_p75,
  CAST(ROUND(SQRT(MAX(0, (b.s2 - b.s * b.s * 1.0 / b.n) / (b.n - 1))), 0) AS INT) AS s_std
FROM bucket_meta b
JOIN p75_vals p ON p.month_year = b.month_year
ORDER BY b.month_year
"""


def query_by_month_stats_pure_sql(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
) -> List[Tuple[str, float, float, int, int]]:
    """
    By-month stats using only SQL (no numpy/Python). Matches commit_statistics_normalized_by_month().
    """
    sql = _sql_by_month_stats(repo_id).strip()
    cur = conn.execute(sql, (repo_id,))
    return [tuple(r) for r in cur.fetchall()]


# --- Parity with cycle_time_by_commits_calculator (same names + _sql, same return shapes) ---

def calculate_time_deltas_sql(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
    logs: Optional[List[Any]] = None,
) -> List[List]:
    """
    SQL version of calculate_time_deltas. Returns same shape: list of [committed_date, cycle_minutes].
    Populates from logs (or git_log() if None) then runs deltas query.
    """
    populate_commits_from_log(conn, logs=logs, repo_id=repo_id)
    rows = query_deltas(conn, repo_id)
    return [[r[0], r[1]] for r in rows]


def commit_statistics_sql(
    conn: sqlite3.Connection,
    bucket_size: int,
    repo_id: str = DEFAULT_REPO_ID,
    logs: Optional[List[Any]] = None,
) -> List[Tuple[str, float, float, int, int]]:
    """
    SQL version of commit_statistics. Same return: list of (interval_start, sum, average, p75, std).
    Populates from logs (or git_log() if None) then runs fixed-bucket query.
    """
    populate_commits_from_log(conn, logs=logs, repo_id=repo_id)
    return query_fixed_bucket_stats_pure_sql(conn, bucket_size, repo_id)


def commit_statistics_normalized_by_month_sql(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
    logs: Optional[List[Any]] = None,
) -> List[Tuple[str, float, float, int, int]]:
    """
    SQL version of commit_statistics_normalized_by_month. Same return shape.
    Populates from logs (or git_log() if None) then runs by-month query.
    """
    populate_commits_from_log(conn, logs=logs, repo_id=repo_id)
    return query_by_month_stats_pure_sql(conn, repo_id)


def cycle_time_between_commits_by_author_sql(
    conn: sqlite3.Connection,
    bucket_size: int = 1000,
    repo_id: str = DEFAULT_REPO_ID,
    logs: Optional[List[Any]] = None,
) -> List[Tuple[str, float, float, int, int]]:
    """
    SQL version of cycle_time_between_commits_by_author. Same return: list of (interval_start, sum, average, p75, std).
    Populates from logs (or git_log() if None) then runs fixed-bucket query.
    """
    populate_commits_from_log(conn, logs=logs, repo_id=repo_id)
    return query_fixed_bucket_stats_pure_sql(conn, bucket_size, repo_id)


# --- Change-failure rate (same keywords as change_failure_calculator) ---

def _sql_change_failure_by_month() -> str:
    """SQL returning (month, rate) for change-failure rate per month. NULL message = not a fix. Keywords match change_failure_calculator."""
    return """
WITH by_month AS (
  SELECT
    strftime('%Y-%m', committed_date, 'unixepoch', 'localtime') AS month,
    COUNT(*) AS total_commits,
    SUM(CASE WHEN (message IS NOT NULL) AND (
      LOWER(message) LIKE '%revert%' OR LOWER(message) LIKE '%hotfix%' OR LOWER(message) LIKE '%bugfix%'
      OR LOWER(message) LIKE '%bug%' OR LOWER(message) LIKE '%fix%' OR LOWER(message) LIKE '%problem%' OR LOWER(message) LIKE '%issue%'
    ) THEN 1 ELSE 0 END) AS fix_commits
  FROM commits
  WHERE _raw_data_params = ?
  GROUP BY month
)
SELECT month,
  CASE WHEN total_commits = 0 THEN 0 ELSE ROUND(100.0 * fix_commits / total_commits, 1) END AS rate
FROM by_month
ORDER BY month
"""


def query_change_failure_by_month_sql(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
) -> List[Tuple[str, float]]:
    """Return list of (month, rate) for change-failure rate. Requires commits already populated (with message)."""
    cur = conn.execute(_sql_change_failure_by_month().strip(), (repo_id,))
    return [(r[0], round(r[1], 1)) for r in cur.fetchall()]


def calculate_change_failure_rate_sql(
    conn: sqlite3.Connection,
    repo_id: str = DEFAULT_REPO_ID,
    logs: Optional[List[Any]] = None,
) -> List[Tuple[str, float]]:
    """
    SQL equivalent of extract_commit_data + calculate_change_failure_rate.
    Populates from logs (or git_log() if None) then runs change-failure query.
    Returns [(month, rate), ...] sorted by month, same shape as CLI expects.
    """
    populate_commits_from_log(conn, logs=logs, repo_id=repo_id)
    return query_change_failure_by_month_sql(conn, repo_id)
