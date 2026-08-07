-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Derived: weekly throughput normalized by “active” authors (legacy throughput_calculator semantics).
-- Matches ``calculate_throughput_per_active_developer_by_week(logs, weeks_back)``:
-- per ISO week: total commits, count of this-week authors who also appear in the rolling
-- window [Monday−weeks_back weeks, next Monday], commits / that count.
-- Requires ``commits_export.period_week``, ``week_monday_unix``, ``week_end_unix``.
-- Upper bound: ``week_end_unix``; lookback: ``local_days_shift`` (timedelta), not ``N*7*86400``.
-- ADR: docs/adr/0006-metrics-throughput-per-active-developer-weekly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_throughput_per_active_developer_weekly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_week TEXT NOT NULL,
    weeks_back INTEGER NOT NULL,
    total_commits INTEGER NOT NULL,
    active_authors_in_week INTEGER NOT NULL,
    throughput_per_active_dev REAL NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_week, weeks_back)
);

CREATE INDEX IF NOT EXISTS idx_metrics_tpadrw_repo_dataset
    ON metrics_throughput_per_active_developer_weekly (repo_slug, dataset_id);

/*
 * Reference materialization (bind :repo_slug, :dataset_id, :weeks_back, :computed_at, …)
 * ---------------------------------------------------------------------------
WITH labeled AS (
  SELECT
    c.author_ref,
    c.committed_at,
    c.period_week,
    c.week_monday_unix,
    c.week_end_unix
  FROM commits_export AS c
  WHERE c.repo_slug = :repo_slug
),
agg AS (
  SELECT
    period_week,
    COUNT(*) AS total_commits,
    MAX(week_monday_unix) AS week_monday_unix,
    MAX(week_end_unix) AS week_end_unix
  FROM labeled
  GROUP BY period_week
),
bounds AS (
  SELECT
    a.period_week,
    a.total_commits,
    a.week_monday_unix,
    a.week_end_unix
  FROM agg AS a
),
with_active AS (
  SELECT
    b.period_week,
    b.total_commits,
    b.week_monday_unix,
    b.week_end_unix,
    (
      SELECT COUNT(DISTINCT l1.author_ref)
      FROM labeled AS l1
      WHERE l1.period_week = b.period_week
        AND EXISTS (
          SELECT 1
          FROM labeled AS l2
          WHERE l2.author_ref = l1.author_ref
            AND l2.committed_at >= local_days_shift(b.week_monday_unix, -(:weeks_back * 7))
            AND l2.committed_at <= b.week_end_unix
        )
    ) AS active_authors_in_week
  FROM bounds AS b
)
SELECT
  :repo_slug,
  :dataset_id,
  wa.period_week,
  :weeks_back,
  wa.total_commits,
  wa.active_authors_in_week,
  CASE
    WHEN wa.active_authors_in_week = 0 THEN 0.0
    ELSE CAST(wa.total_commits AS REAL) / wa.active_authors_in_week
  END AS throughput_per_active_dev,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM with_active AS wa
ORDER BY wa.period_week;
 */
