-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``); portable SQL (no UDFs).
-- Matches ``throughput_calculator.calculate_throughput_per_active_developer(logs, weeks_back)``.
-- Month bucket: same calendar month as ``extract_commits_and_authors``; ``period_month`` is ``YYYY-MM``
-- (minimal formatting vs legacy unpadded month keys).
-- Activity scan: ``cutoff <= committed_at <= month_start`` with ``month_start`` = first day 00:00 local
-- (same as legacy ``datetime(y,m,1)`` vs ``commit_date``).
-- ``active_authors_in_month`` = month authors ∩ authors with ≥1 commit in that window; throughput = commits / count.
-- Month start as unix: ``CAST(strftime('%s', printf('%04d-%02d-01 00:00:00', y, m), 'utc') AS INTEGER)``
-- mirrors Python ``int(datetime(y, m, 1).timestamp())`` (SQLite ``'utc'`` modifier: timestring is local wall time).
-- ADR: docs/adr/0007-metrics-throughput-per-active-developer-monthly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_throughput_per_active_developer_monthly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_month TEXT NOT NULL,
    weeks_back INTEGER NOT NULL,
    total_commits INTEGER NOT NULL,
    active_authors_in_month INTEGER NOT NULL,
    throughput_per_active_dev REAL NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_month, weeks_back)
);

CREATE INDEX IF NOT EXISTS idx_metrics_tpadrm_repo_dataset
    ON metrics_throughput_per_active_developer_monthly (repo_slug, dataset_id);

/*
 * Reference materialization (bind :repo_slug, :dataset_id, :weeks_back, :computed_at, …)
 * ---------------------------------------------------------------------------
WITH labeled AS (
  SELECT
    c.author_ref,
    c.committed_at,
    strftime('%Y-%m', c.committed_at, 'unixepoch', 'localtime') AS period_month
  FROM commits_export AS c
  WHERE c.repo_slug = :repo_slug
),
agg AS (
  SELECT
    period_month,
    COUNT(*) AS total_commits,
    CAST(substr(period_month, 1, 4) AS INTEGER) AS y,
    CAST(substr(period_month, 6, 2) AS INTEGER) AS m
  FROM labeled
  GROUP BY period_month
),
bounds AS (
  SELECT
    a.period_month,
    a.total_commits,
    a.y,
    a.m,
    CAST(
      strftime(
        '%s',
        printf('%04d-%02d-01 00:00:00', CAST(a.y AS INTEGER), CAST(a.m AS INTEGER)),
        'utc'
      ) AS INTEGER
    ) AS month_start_unix
  FROM agg AS a
),
with_active AS (
  SELECT
    b.period_month,
    b.total_commits,
    (
      SELECT COUNT(DISTINCT l1.author_ref)
      FROM labeled AS l1
      WHERE l1.period_month = b.period_month
        AND EXISTS (
          SELECT 1
          FROM labeled AS l2
          WHERE l2.author_ref = l1.author_ref
            AND l2.committed_at >= b.month_start_unix - (:weeks_back * 7 * 86400)
            AND l2.committed_at <= b.month_start_unix
        )
    ) AS active_authors_in_month
  FROM bounds AS b
)
SELECT
  :repo_slug,
  :dataset_id,
  wa.period_month,
  :weeks_back,
  wa.total_commits,
  wa.active_authors_in_month,
  CASE
    WHEN wa.active_authors_in_month = 0 THEN 0.0
    ELSE CAST(wa.total_commits AS REAL) / wa.active_authors_in_month
  END AS throughput_per_active_dev,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM with_active AS wa
ORDER BY wa.period_month;
 */
