-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Derived: monthly commit volume and distinct author_ref count.
-- ADR: docs/adr/0005-metrics-throughput-monthly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_throughput_monthly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_month TEXT NOT NULL,
    commit_count INTEGER NOT NULL,
    distinct_author_count INTEGER NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_month)
);

CREATE INDEX IF NOT EXISTS idx_metrics_thr_repo_dataset
    ON metrics_throughput_monthly (repo_slug, dataset_id);

/*
 * Reference: materialization (bind :repo_slug, :dataset_id, :computed_at, etc.)
 * ---------------------------------------------------------------------------
INSERT INTO metrics_throughput_monthly (
  repo_slug, dataset_id, period_month, commit_count, distinct_author_count,
  source_commits_schema_version, computed_at, tenant_id
)
SELECT
  :repo_slug,
  :dataset_id,
  m.period_month,
  COUNT(*) AS commit_count,
  COUNT(DISTINCT m.author_ref) AS distinct_author_count,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM (
  SELECT
    author_ref,
    strftime('%Y-%m', committed_at, 'unixepoch', 'localtime') AS period_month
  FROM commits_export
  WHERE repo_slug = :repo_slug
) AS m
GROUP BY m.period_month;
 */
