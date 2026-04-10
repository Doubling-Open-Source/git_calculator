-- Derived: monthly cycle-time statistics over per-author LAG deltas (minutes).
-- Aligns with sqlite_lake _sql_by_month_stats (partition by author, order by time, sha).
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
  SELECT sha, author_ref, committed_at
  FROM commits_export
  WHERE repo_slug = :repo_slug
),
deltas AS (
  SELECT committed_at,
    ROUND((committed_at - LAG(committed_at) OVER (
      PARTITION BY author_ref ORDER BY committed_at, sha
    )) / 60.0, 2) AS cycle_minutes
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
    b.frac
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
  CAST(ROUND((1.0 - p.frac) * p.v_lo + p.frac * COALESCE(p.v_hi, p.v_lo), 0) AS INT) AS p75_cycle_minutes,
  CAST(ROUND(SQRT(MAX(0, (b.s2 - b.s * b.s * 1.0 / b.n) / (b.n - 1))), 0) AS INT) AS std_cycle_minutes,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM bucket_meta b
JOIN p75_vals p ON p.month_year = b.month_year
ORDER BY b.month_year;
 */
