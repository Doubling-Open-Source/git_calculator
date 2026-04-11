-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``); portable SQL (no UDFs).
-- Derived: per ISO week, total commits in that week and count of distinct authors with ≥1 commit
-- in the rolling window [Monday−weeks_back weeks, next Monday 00:00] inclusive in local time — matching
-- ``calculate_active_developers_by_week`` (not intersection semantics; see ADR 0006 vs 0008).
-- Requires ``commits_export.period_week`` and ``commits_export.week_monday_unix`` (populated by the exporter;
-- same semantics as legacy ``datetime.fromtimestamp`` / ``isocalendar``).
-- ADR: docs/adr/0008-metrics-active-developers-weekly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_active_developers_weekly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_week TEXT NOT NULL,
    weeks_back INTEGER NOT NULL,
    total_commits INTEGER NOT NULL,
    active_developer_count INTEGER NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_week, weeks_back)
);

CREATE INDEX IF NOT EXISTS idx_metrics_adw_repo_dataset
    ON metrics_active_developers_weekly (repo_slug, dataset_id);

/*
 * Reference materialization (bind :repo_slug, :dataset_id, :weeks_back, :computed_at, …)
 * ---------------------------------------------------------------------------
WITH labeled AS (
  SELECT
    c.author_ref,
    c.committed_at,
    c.period_week,
    c.week_monday_unix
  FROM commits_export AS c
  WHERE c.repo_slug = :repo_slug
),
agg AS (
  SELECT
    period_week,
    COUNT(*) AS total_commits,
    MAX(week_monday_unix) AS week_monday_unix
  FROM labeled
  GROUP BY period_week
),
bounds AS (
  SELECT
    a.period_week,
    a.total_commits,
    a.week_monday_unix
  FROM agg AS a
),
rolling AS (
  SELECT
    b.period_week,
    b.total_commits,
    (
      SELECT COUNT(DISTINCT l.author_ref)
      FROM labeled AS l
      WHERE l.committed_at >= b.week_monday_unix - (:weeks_back * 7 * 86400)
        AND l.committed_at <= b.week_monday_unix + (7 * 86400)
    ) AS active_developer_count
  FROM bounds AS b
)
SELECT
  :repo_slug,
  :dataset_id,
  r.period_week,
  :weeks_back,
  r.total_commits,
  r.active_developer_count,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM rolling AS r
ORDER BY r.period_week;
 */
