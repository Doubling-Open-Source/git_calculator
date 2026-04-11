-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Per-author commit totals and ``calculate_percentiles``-style distribution (pandas ``rank(method='max')`` / N * 100).
-- ``as_of_period`` = ``all`` = one row set per author for the full export snapshot (dataset-scoped).
-- ADR: docs/adr/0009-metrics-author-commit-percentiles.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_author_commit_percentiles (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    as_of_period TEXT NOT NULL,
    author_ref TEXT NOT NULL,
    commit_count INTEGER NOT NULL,
    author_commit_percentile REAL NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, as_of_period, author_ref)
);

CREATE INDEX IF NOT EXISTS idx_metrics_acp_repo_dataset_period
    ON metrics_author_commit_percentiles (repo_slug, dataset_id, as_of_period);

/*
 * Reference: materialization (bind :repo_slug, :dataset_id, :computed_at, etc.)
 * ---------------------------------------------------------------------------
INSERT INTO metrics_author_commit_percentiles (
  repo_slug, dataset_id, as_of_period, author_ref, commit_count, author_commit_percentile,
  source_commits_schema_version, computed_at, tenant_id
)
WITH totals AS (
  SELECT author_ref, COUNT(*) AS commit_count
  FROM commits_export
  WHERE repo_slug = :repo_slug
  GROUP BY author_ref
),
n_auth AS (
  SELECT COUNT(*) AS n FROM totals
)
SELECT
  :repo_slug,
  :dataset_id,
  'all' AS as_of_period,
  t.author_ref,
  t.commit_count,
  (
    (SELECT COUNT(*) FROM totals t2 WHERE t2.commit_count < t.commit_count)
    + (SELECT COUNT(*) FROM totals t3 WHERE t3.commit_count = t.commit_count)
  ) * 100.0 / (SELECT n FROM n_auth) AS author_commit_percentile,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM totals t;
 */
