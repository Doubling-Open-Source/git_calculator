-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``); requires UDF ``iso_week_monday_unix``.
-- Derived: per ISO week, total commits in that week and count of distinct authors with ≥1 commit
-- in the rolling window [Monday−weeks_back weeks, next Monday 00:00] inclusive in local time — matching
-- ``calculate_active_developers_by_week`` (not intersection semantics; see ADR 0006 vs 0008).
-- Materialization requires SQLite function ``iso_week_monday_unix(iso_year, iso_week)`` returning
-- unix seconds for Monday 00:00 local (``datetime.fromisocalendar(y, w, 1)``); the validation
-- runner registers it before executing this SELECT.
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
    strftime('%G', c.committed_at, 'unixepoch', 'localtime') || '-W' ||
      printf('%02d', CAST(strftime('%V', c.committed_at, 'unixepoch', 'localtime') AS INT)) AS period_week
  FROM commits_export AS c
  WHERE c.repo_slug = :repo_slug
),
agg AS (
  SELECT
    period_week,
    COUNT(*) AS total_commits,
    CAST(substr(period_week, 1, 4) AS INTEGER) AS iso_y,
    CAST(substr(period_week, 7, 2) AS INTEGER) AS iso_w
  FROM labeled
  GROUP BY period_week
),
bounds AS (
  SELECT
    a.period_week,
    a.total_commits,
    a.iso_y,
    a.iso_w,
    iso_week_monday_unix(a.iso_y, a.iso_w) AS week_monday_unix
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
