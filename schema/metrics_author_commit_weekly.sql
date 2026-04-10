-- Derived: per-author weekly commit counts (ISO week label YYYY-Www via strftime %G / %V).
-- Week bucket uses commit local calendar; label is ISO year-week (Monday-based weeks).
-- ADR: docs/adr/0006-metrics-author-commit-weekly.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_author_commit_weekly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_week TEXT NOT NULL,
    author_ref TEXT NOT NULL,
    commit_count INTEGER NOT NULL,
    first_committed_at INTEGER,
    last_committed_at INTEGER,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_week, author_ref)
);

CREATE INDEX IF NOT EXISTS idx_metrics_acw_repo_dataset_author
    ON metrics_author_commit_weekly (repo_slug, dataset_id, author_ref);

/*
 * Reference: materialization (bind :repo_slug, :dataset_id, :computed_at, etc.)
 * period_week = strftime('%G', ts, 'unixepoch', 'localtime') || '-W' ||
 *               printf('%02d', CAST(strftime('%V', ts, 'unixepoch', 'localtime') AS INT))
 * ---------------------------------------------------------------------------
INSERT INTO metrics_author_commit_weekly (
  repo_slug, dataset_id, period_week, author_ref, commit_count,
  first_committed_at, last_committed_at,
  source_commits_schema_version, computed_at, tenant_id
)
SELECT
  :repo_slug,
  :dataset_id,
  strftime('%G', c.committed_at, 'unixepoch', 'localtime') || '-W' ||
    printf('%02d', CAST(strftime('%V', c.committed_at, 'unixepoch', 'localtime') AS INT)) AS period_week,
  c.author_ref,
  COUNT(*) AS commit_count,
  MIN(c.committed_at) AS first_committed_at,
  MAX(c.committed_at) AS last_committed_at,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM commits_export AS c
WHERE c.repo_slug = :repo_slug
GROUP BY
  strftime('%G', c.committed_at, 'unixepoch', 'localtime') || '-W' ||
    printf('%02d', CAST(strftime('%V', c.committed_at, 'unixepoch', 'localtime') AS INT)),
  c.author_ref;
 */
