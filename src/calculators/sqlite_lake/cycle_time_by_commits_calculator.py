"""
SQLite cycle-time queries mirroring cycle_time_by_commits_calculator.
Pure SQL (no numpy/Python for aggregates). Same return shapes for parity tests.
See docs/lake_schema_for_sqlite.md.

Python vs SQL differences (docs/cycle_time_python_vs_sql_differences.md):
- Ordering: Python uses git log order; SQL uses ORDER BY committed_date, sha.
  When multiple commits share the same committed_date per author, pairing can differ
  (e.g. 60-min delta swap) and cascade to fixed-bucket and by-month stats.
- By-month: timestamp boundary / TZ can shift a delta between months (Python vs SQL).
- Float rounding: minor differences in intermediate values may appear.
"""

import sqlite3
from typing import List, Tuple


def _deltas_cte() -> str:
    """
    SQL for cycle-time deltas between consecutive commits per author.
    LAG() gives previous commit timestamp; diff / 60 = minutes. First row per author has NULL.
    Tie-break: ORDER BY committed_date, sha (Option B) for stable SQL; Python uses git log order.
    DIFF: When duplicate (author_email, committed_date) exist, pairing can differ (SQL by sha vs Python by log).
    """
    return """
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


def query_deltas(conn: sqlite3.Connection, repo_id: str) -> List[Tuple[int, float]]:
    """Return list of (committed_date_unix, cycle_minutes) matching Python calculate_time_deltas order."""
    cur = conn.execute(_deltas_cte().strip(), (repo_id,))
    rows = cur.fetchall()
    return [(r[0], round(r[1], 2)) for r in rows]


def query_deltas_raw(conn: sqlite3.Connection, repo_id: str) -> List[Tuple[int, float]]:
    """Same as query_deltas but return raw rows for debugging (no rounding)."""
    cur = conn.execute(_deltas_cte().strip(), (repo_id,))
    return [(r[0], r[1]) for r in cur.fetchall()]


def _sql_fixed_bucket_stats(bucket_size: int) -> str:
    """
    Fixed-bucket stats (commit_statistics equivalent). Pure SQL, no numpy.
    p75: numpy-style linear interpolation: index = (n-1)*0.75; p75 = (1-frac)*v_lo + frac*v_hi.
    stdev: sample stdev = SQRT(SUM((x-mean)^2)/(n-1)); via SUM(x^2)-n*mean^2.
    DIFF: Any delta pairing differences (from _deltas_cte ordering) cascade to sum/avg/p75/std.
    """
    return """
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
-- bucket_id = (row_num - 1) / bucket_size; sha kept for stable tie-break
numbered AS (
  SELECT committed_date, cycle_minutes,
    (ROW_NUMBER() OVER (ORDER BY committed_date, sha) - 1) / ? AS bucket_id,
    ROW_NUMBER() OVER (ORDER BY committed_date, sha) AS rn_global
  FROM valid
),
-- k_lo, frac for p75 linear interpolation; s2 for stdev (SUM(x^2)-n*mean^2)
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
    repo_id: str,
) -> List[Tuple[str, float, float, int, int]]:
    """Fixed-bucket stats using only SQL. Matches commit_statistics()."""
    sql = _sql_fixed_bucket_stats(bucket_size).strip()
    cur = conn.execute(sql, (repo_id, bucket_size))
    return [tuple(r) for r in cur.fetchall()]


def _sql_by_month_stats() -> str:
    """
    By-month stats (commit_statistics_normalized_by_month equivalent).
    Same p75 and stdev logic as fixed-bucket; buckets are calendar months (YYYY-MM).
    DIFF: Delta ordering differences cascade here; also timestamp boundary/TZ can assign a delta
    to a different month (strftime localtime vs Python datetime.fromtimestamp).
    """
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
    repo_id: str,
) -> List[Tuple[str, float, float, int, int]]:
    """By-month stats using only SQL. Matches commit_statistics_normalized_by_month()."""
    sql = _sql_by_month_stats().strip()
    cur = conn.execute(sql, (repo_id,))
    return [tuple(r) for r in cur.fetchall()]


def _sql_cycle_time_chart() -> str:
    """Chart-ready cycle time. Prepare (minutes→days) in SQL. Standalone for MySQL port."""
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
),
stats AS (
  SELECT
    b.month_year,
    CAST(ROUND((1.0 - p.frac) * p.v_lo + p.frac * COALESCE(p.v_hi, p.v_lo), 0) AS INT) AS s_p75,
    CAST(ROUND(SQRT(MAX(0, (b.s2 - b.s * b.s * 1.0 / b.n) / (b.n - 1))), 0) AS INT) AS s_std
  FROM bucket_meta b
  JOIN p75_vals p ON p.month_year = b.month_year
)
SELECT
  month_year AS month,
  CAST(s_p75 AS REAL) / 1440.0 AS p75_days,
  CAST(s_std AS REAL) / 1440.0 AS std_days
FROM stats
ORDER BY month_year
"""


def query_cycle_time_chart_sql(
    conn: sqlite3.Connection,
    repo_id: str,
) -> List[Tuple[str, float, float]]:
    """Chart-ready cycle time: (month, p75_days, std_days). Prepare done in SQL. Requires commits populated."""
    cur = conn.execute(_sql_cycle_time_chart().strip(), (repo_id,))
    return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def get_cycle_time_chart_data_sql(
    conn: sqlite3.Connection,
    repo_id: str,
) -> List[Tuple[str, float, float]]:
    """Chart-ready cycle time. Requires commits already populated."""
    return query_cycle_time_chart_sql(conn, repo_id)


def calculate_time_deltas_sql(
    conn: sqlite3.Connection,
    repo_id: str,
) -> List[List]:
    """SQL version of calculate_time_deltas. Same shape: list of [committed_date, cycle_minutes]. Requires commits populated."""
    rows = query_deltas(conn, repo_id)
    return [[r[0], r[1]] for r in rows]


def commit_statistics_sql(
    conn: sqlite3.Connection,
    bucket_size: int,
    repo_id: str,
) -> List[Tuple[str, float, float, int, int]]:
    """SQL version of commit_statistics. Requires commits populated."""
    return query_fixed_bucket_stats_pure_sql(conn, bucket_size, repo_id)


def commit_statistics_normalized_by_month_sql(
    conn: sqlite3.Connection,
    repo_id: str,
) -> List[Tuple[str, float, float, int, int]]:
    """SQL version of commit_statistics_normalized_by_month. Requires commits populated."""
    return query_by_month_stats_pure_sql(conn, repo_id)


def cycle_time_between_commits_by_author_sql(
    conn: sqlite3.Connection,
    repo_id: str,
    bucket_size: int = 1000,
) -> List[Tuple[str, float, float, int, int]]:
    """SQL version of cycle_time_between_commits_by_author. Requires commits populated."""
    return query_fixed_bucket_stats_pure_sql(conn, bucket_size, repo_id)
