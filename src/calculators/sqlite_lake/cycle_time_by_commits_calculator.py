"""
SQLite cycle-time queries mirroring cycle_time_by_commits_calculator.
Pure SQL (no numpy/Python for aggregates). Same return shapes for parity tests.
See docs/lake_schema_for_sqlite.md.

Reader's guide
--------------
1. Populate (``schema.populate_commits_from_log``) writes ``log_ordinal`` = index in
   ``git_log()`` (0 = newest). Same contract as ``commits_export.log_ordinal``.
2. Per-author gaps: window ``ORDER BY log_ordinal DESC`` so rows walk **oldest → newest**;
   ``LAG(committed_date)`` is the previous (older) commit; first row per author is NULL.
3. Minutes use **local wall clock** (``julianday(... 'localtime')``), not raw unix/60,
   so DST spans match Python ``datetime.fromtimestamp`` deltas.
4. Fixed-bucket / by-month / chart CTEs reuse that delta step, then aggregate
   (p75 = numpy-style linear interpolation; stdev = sample stdev).

``log_ordinal`` is a **local SqliteLake extension** beyond stock DevLake ``lake.commits``.
Legacy ``ORDER BY committed_date, sha`` is :func:`query_deltas_legacy_by_committed_date`
(warns: breaks the ordinal contract).

Remaining gaps: docs/cycle_time_python_vs_sql_differences.md.
"""

from __future__ import annotations

import sqlite3
import warnings
from typing import List, Tuple

LAKE_CYCLE_TIME_LEGACY_NO_LOG_ORDINAL_WARNING = (
    "SqliteLake legacy cycle-time SQL uses ORDER BY committed_date, sha without "
    "log_ordinal. That breaks backwards compatibility with the git_log / "
    "commits_export ordinal contract. Prefer the happy path (populate via "
    "load_logs so log_ordinal is set; query_deltas / fixed-bucket / by-month). "
    "See docs/cycle_time_python_vs_sql_differences.md."
)

# Back-compat alias for the previous constant name.
LAKE_CYCLE_TIME_NO_LOG_ORDINAL_WARNING = LAKE_CYCLE_TIME_LEGACY_NO_LOG_ORDINAL_WARNING

_warned_lake_cycle_time_legacy_no_log_ordinal = False

# Shared fragment: wall-clock minutes between this row and LAG (older) commit.
# Bindings: none — used inside PARTITION BY author … ORDER BY log_ordinal DESC windows.
_CYCLE_MINUTES_JULIANDAY = """
    ROUND((
      julianday(datetime(committed_date, 'unixepoch', 'localtime'))
      - julianday(datetime(
          LAG(committed_date) OVER (
            PARTITION BY author_email ORDER BY log_ordinal DESC
          ),
          'unixepoch', 'localtime'
        ))
    ) * 24 * 60, 2)
""".strip()


def warn_lake_cycle_time_no_log_ordinal(*, stacklevel: int = 2) -> None:
    """Warn once per process that a legacy (non-ordinal) lake cycle-time path was used."""
    global _warned_lake_cycle_time_legacy_no_log_ordinal
    if _warned_lake_cycle_time_legacy_no_log_ordinal:
        return
    _warned_lake_cycle_time_legacy_no_log_ordinal = True
    warnings.warn(
        LAKE_CYCLE_TIME_LEGACY_NO_LOG_ORDINAL_WARNING,
        UserWarning,
        stacklevel=stacklevel,
    )


def _deltas_cte() -> str:
    """
    One row per inter-commit gap for each author (happy path).

    Steps in SQL:
    - Filter repo via ``_raw_data_params``.
    - Window oldest→newest with ``ORDER BY log_ordinal DESC`` (0=newest → DESC puts
      large ordinals first).
    - Minutes = local julianday gap (DST-safe vs python fromtimestamp).
    - Drop the first commit per author (LAG NULL → cycle_minutes NULL).
    """
    return f"""
-- Happy-path deltas: git_log order + local wall-clock minutes.
WITH ordered AS (
  SELECT sha, author_email, committed_date, log_ordinal
  FROM commits
  WHERE _raw_data_params = ?
),
deltas AS (
  SELECT
    committed_date,
    -- log_ordinal DESC: walk oldest→newest; LAG = older commit.
    -- julianday(localtime): match Python timedelta across DST (not unix/60).
    {_CYCLE_MINUTES_JULIANDAY} AS cycle_minutes
  FROM ordered
)
SELECT committed_date, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
"""


def _deltas_cte_legacy_by_committed_date() -> str:
    """
    Legacy pairing: timestamp then sha (deterministic, not git_log order on ties).

    Prefer :func:`query_deltas`. This path exists for DevLake-shaped DBs without ordinals.
    """
    return """
-- LEGACY: no log_ordinal — ties break by sha, not git_log order.
WITH ordered AS (
  SELECT sha, author_email, committed_date
  FROM commits
  WHERE _raw_data_params = ?
),
deltas AS (
  SELECT
    committed_date,
    ROUND((
      julianday(datetime(committed_date, 'unixepoch', 'localtime'))
      - julianday(datetime(
          LAG(committed_date) OVER (
            PARTITION BY author_email ORDER BY committed_date, sha
          ),
          'unixepoch', 'localtime'
        ))
    ) * 24 * 60, 2) AS cycle_minutes
  FROM ordered
)
SELECT committed_date, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
"""


def query_deltas(conn: sqlite3.Connection, repo_id: str) -> List[Tuple[int, float]]:
    """Return list of (committed_date_unix, cycle_minutes) using log_ordinal pairing."""
    cur = conn.execute(_deltas_cte().strip(), (repo_id,))
    rows = cur.fetchall()
    return [(r[0], round(r[1], 2)) for r in rows]


def query_deltas_legacy_by_committed_date(
    conn: sqlite3.Connection, repo_id: str
) -> List[Tuple[int, float]]:
    """Legacy deltas: ORDER BY committed_date, sha (warns; not ordinal-correct)."""
    warn_lake_cycle_time_no_log_ordinal(stacklevel=2)
    cur = conn.execute(_deltas_cte_legacy_by_committed_date().strip(), (repo_id,))
    rows = cur.fetchall()
    return [(r[0], round(r[1], 2)) for r in rows]


def _sql_fixed_bucket_stats(bucket_size: int) -> str:
    """
    Fixed-size buckets of deltas (``commit_statistics``), pure SQL.

    Pipeline:
    1. Deltas as in :func:`_deltas_cte` (plus author_ord / child_ord for sort stability).
    2. Sort like Python ``sorted(time_deltas, key=timestamp)`` with a stable tie-break:
       author first-seen in git_log (``MIN(log_ordinal)``) then child ``log_ordinal``.
    3. Assign ``bucket_id = (row_number - 1) / bucket_size``.
    4. Per bucket: sum, mean, p75 (linear interp), sample stdev — same formulas as Python/numpy.
    """
    # bucket_size is bound as ``?`` at execute time (see query_fixed_bucket_stats_pure_sql).
    return f"""
-- Fixed-bucket stats (parity with commit_statistics).
WITH ordered AS (
  SELECT sha, author_email, committed_date, log_ordinal
  FROM commits WHERE _raw_data_params = ?
),
-- author_ord: first appearance in git_log (matches Python author_map insertion order).
author_first AS (
  SELECT author_email, MIN(log_ordinal) AS author_ord
  FROM ordered
  GROUP BY author_email
),
deltas AS (
  SELECT o.committed_date, o.sha, o.log_ordinal AS child_ord, af.author_ord,
    ROUND((
      julianday(datetime(o.committed_date, 'unixepoch', 'localtime'))
      - julianday(datetime(
          LAG(o.committed_date) OVER (
            PARTITION BY o.author_email ORDER BY o.log_ordinal DESC
          ),
          'unixepoch', 'localtime'
        ))
    ) * 24 * 60, 2) AS cycle_minutes
  FROM ordered o
  JOIN author_first af ON af.author_email = o.author_email
),
valid AS (
  SELECT committed_date, child_ord, author_ord, cycle_minutes
  FROM deltas WHERE cycle_minutes IS NOT NULL
),
-- Stable sort key ≈ Python sorted(deltas, key=ts) after emission order (author_ord, child_ord).
numbered AS (
  SELECT committed_date, cycle_minutes,
    (ROW_NUMBER() OVER (
      ORDER BY committed_date, author_ord, child_ord
    ) - 1) / ? AS bucket_id,
    ROW_NUMBER() OVER (
      ORDER BY committed_date, author_ord, child_ord
    ) AS rn_global
  FROM valid
),
bucket_meta AS (
  SELECT bucket_id,
    MIN(committed_date) AS first_ts,
    SUM(cycle_minutes) AS s,
    SUM(cycle_minutes * cycle_minutes) AS s2,  -- for sample variance via E[x^2]-mean^2
    COUNT(*) AS n,
    -- p75 linear interpolation index: k_lo = floor((n-1)*0.75)+1 (1-based rn)
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
-- p75 = (1-frac)*v_lo + frac*v_hi at ranks k_lo and k_lo+1 (numpy percentile style).
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
  -- sample stdev: sqrt( sum((x-mean)^2) / (n-1) )
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
    Calendar-month buckets (``commit_statistics_normalized_by_month``).

    Same delta + p75/stdev math as fixed-bucket; grouping key is YYYY-MM of the
    child commit (localtime), not a fixed row count.
    """
    return f"""
-- By-month stats (parity with commit_statistics_normalized_by_month).
WITH ordered AS (
  SELECT sha, author_email, committed_date, log_ordinal
  FROM commits WHERE _raw_data_params = ?
),
deltas AS (
  SELECT committed_date,
    {_CYCLE_MINUTES_JULIANDAY} AS cycle_minutes
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
    """
    Chart-ready by-month p75/stdev in **days** (minutes / 1440).

    Same delta and monthly aggregate path as :func:`_sql_by_month_stats`; only the
    final SELECT converts units.
    """
    return f"""
-- Chart series: monthly p75_days / std_days (prepare done in SQL).
WITH ordered AS (
  SELECT sha, author_email, committed_date, log_ordinal
  FROM commits WHERE _raw_data_params = ?
),
deltas AS (
  SELECT committed_date,
    {_CYCLE_MINUTES_JULIANDAY} AS cycle_minutes
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
  CAST(s_p75 AS REAL) / 1440.0 AS p75_days,  -- minutes → days
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
