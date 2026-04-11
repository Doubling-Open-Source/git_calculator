-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Derived: monthly change-failure-style rate from commits_export keyword flags.
-- ADR: docs/adr/0002-metrics-change-failure-monthly.md
-- Fix-like: (subject_has_keywords OR body_has_keywords) = 1 (not full-message LIKE).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_change_failure_monthly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_month TEXT NOT NULL,
    total_commits INTEGER NOT NULL,
    fix_like_commits INTEGER NOT NULL,
    rate_percent REAL NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_month)
);

CREATE INDEX IF NOT EXISTS idx_metrics_cf_repo_dataset
    ON metrics_change_failure_monthly (repo_slug, dataset_id);

/*
 * Reference: materialization from commits_export
 * Bind: :repo_slug, :dataset_id, :computed_at (and optional :tenant_id, :source_ver)
 * ---------------------------------------------------------------------------
INSERT INTO metrics_change_failure_monthly (
  repo_slug, dataset_id, period_month, total_commits, fix_like_commits, rate_percent,
  source_commits_schema_version, computed_at, tenant_id
)
SELECT
  :repo_slug,
  :dataset_id,
  m.period_month,
  m.total_commits,
  m.fix_like_commits,
  CASE WHEN m.total_commits = 0 THEN 0.0
       ELSE ROUND(100.0 * m.fix_like_commits * 1.0 / m.total_commits, 1) END,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM (
  SELECT
    strftime('%Y-%m', committed_at, 'unixepoch', 'localtime') AS period_month,
    COUNT(*) AS total_commits,
    SUM(CASE WHEN subject_has_keywords = 1 OR body_has_keywords = 1 THEN 1 ELSE 0 END) AS fix_like_commits
  FROM commits_export
  WHERE repo_slug = :repo_slug
  GROUP BY period_month
) AS m;
 */
