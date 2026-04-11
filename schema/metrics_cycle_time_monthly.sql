-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Derived: monthly cycle-time statistics over per-author LAG deltas (minutes).
-- LAG order: commits_export.log_ordinal (git_log iteration order).
-- cycle_minutes: matches cycle_time_by_commits_calculator.calculate_time_deltas — naive local
-- datetimes from unix epochs, so wall‑clock timedelta (not raw (Δunix)/60 across DST jumps).
-- Use julianday(datetime(...,'localtime')) difference × 24×60; see metrics_cycle_time_monthly.py.
-- ADR: docs/adr/0003-metrics-cycle-time-monthly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_cycle_time_monthly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_month TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    sum_cycle_minutes REAL NOT NULL,
    avg_cycle_minutes REAL NOT NULL,
    p75_cycle_minutes INTEGER NOT NULL,
    std_cycle_minutes INTEGER NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_month)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ctm_repo_dataset
    ON metrics_cycle_time_monthly (repo_slug, dataset_id);

/*
 * Reference: materialization SELECT (bind :repo_slug, :dataset_id, :computed_at, etc.)
 * Wrap final SELECT as INSERT INTO metrics_cycle_time_monthly (...) SELECT ...
 * ---------------------------------------------------------------------------
WITH ordered AS (
  SELECT sha, author_ref, committed_at, log_ordinal
  FROM commits_export
  WHERE repo_slug = :repo_slug
),
deltas AS (
  SELECT committed_at,
    ROUND((
      julianday(datetime(committed_at, 'unixepoch', 'localtime'))
      - julianday(datetime(
          LAG(committed_at) OVER (
            PARTITION BY author_ref ORDER BY log_ordinal DESC
          ),
          'unixepoch', 'localtime'
        ))
    ) * 24 * 60, 2) AS cycle_minutes
  FROM ordered
),
valid AS (
  SELECT committed_at, cycle_minutes FROM deltas WHERE cycle_minutes IS NOT NULL
),
with_month AS (
  SELECT committed_at, cycle_minutes,
    strftime('%Y-%m', committed_at, 'unixepoch', 'localtime') AS month_year
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
    b.frac,
    (1.0 - b.frac) * MAX(CASE WHEN r.rn = b.k_lo THEN r.cycle_minutes END)
      + b.frac * COALESCE(
        MAX(CASE WHEN r.rn = b.k_lo + 1 THEN r.cycle_minutes END),
        MAX(CASE WHEN r.rn = b.k_lo THEN r.cycle_minutes END)
      ) AS p75_linear
  FROM bucket_meta b
  LEFT JOIN ranked r ON r.month_year = b.month_year AND r.rn IN (b.k_lo, b.k_lo + 1)
  GROUP BY b.month_year, b.frac
)
SELECT
  :repo_slug,
  :dataset_id,
  b.month_year AS period_month,
  b.n AS sample_count,
  b.s AS sum_cycle_minutes,
  ROUND(b.s / b.n, 2) AS avg_cycle_minutes,
  /* int(round(x,0)) in Python is half-to-even; SQLite ROUND() is half-away-from-zero */
  CAST(
    CASE
      WHEN p.p75_linear - CAST(p.p75_linear AS INT) < 0.5 THEN CAST(p.p75_linear AS INT)
      WHEN p.p75_linear - CAST(p.p75_linear AS INT) > 0.5 THEN CAST(p.p75_linear AS INT) + 1
      ELSE CASE WHEN CAST(p.p75_linear AS INT) % 2 = 0 THEN CAST(p.p75_linear AS INT)
           ELSE CAST(p.p75_linear AS INT) + 1 END
    END AS INT
  ) AS p75_cycle_minutes,
  CAST(ROUND(SQRT(MAX(0, (b.s2 - b.s * b.s * 1.0 / b.n) / (b.n - 1))), 0) AS INT) AS std_cycle_minutes,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM bucket_meta b
JOIN p75_vals p ON p.month_year = b.month_year
ORDER BY b.month_year;
 */
