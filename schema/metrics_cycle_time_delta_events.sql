-- IMPLEMENTED — materialization validated by ``schema_metrics`` (see ``sqlite_lake/schema_metrics``).
-- Derived: one row per non-null inter-commit gap (minutes) per author_ref.
-- ADR: docs/adr/0004-metrics-cycle-time-delta-events.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_cycle_time_delta_events (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    author_ref TEXT NOT NULL,
    committed_at INTEGER NOT NULL,
    child_sha TEXT NOT NULL,
    cycle_minutes REAL NOT NULL,
    prev_sha TEXT,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, author_ref, committed_at, child_sha)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ctd_repo_author
    ON metrics_cycle_time_delta_events (repo_slug, dataset_id, author_ref);

/*
 * Reference: materialization from commits_export
 * Bind: :repo_slug, :dataset_id, :computed_at, :source_commits_schema_version, :tenant_id
 *
 * Pairing steps (same idea as SqliteLake happy-path deltas):
 *   1. log_ordinal: 0 = newest in git_log; ORDER BY log_ordinal DESC walks oldest→newest.
 *   2. LAG(committed_at) = previous (older) commit for that author_ref.
 *   3. Minutes = local julianday gap (DST-aware), not raw unix seconds / 60.
 *   4. Drop rows where LAG is NULL (first commit per author).
 * ---------------------------------------------------------------------------
INSERT INTO metrics_cycle_time_delta_events (
  repo_slug, dataset_id, author_ref, committed_at, child_sha, cycle_minutes, prev_sha,
  source_commits_schema_version, computed_at, tenant_id
)
SELECT
  :repo_slug,
  :dataset_id,
  d.author_ref,
  d.committed_at,
  d.child_sha,
  d.cycle_minutes,
  d.prev_sha,
  :source_commits_schema_version,
  :computed_at,
  :tenant_id
FROM (
  SELECT
    author_ref,
    committed_at,
    sha AS child_sha,
    -- Wall-clock minutes between this commit and LAG (older) in log order.
    ROUND((
      julianday(datetime(committed_at, 'unixepoch', 'localtime'))
      - julianday(datetime(
          LAG(committed_at) OVER (
            PARTITION BY author_ref ORDER BY log_ordinal DESC
          ),
          'unixepoch', 'localtime'
        ))
    ) * 24 * 60, 2) AS cycle_minutes,
    LAG(sha) OVER (PARTITION BY author_ref ORDER BY log_ordinal DESC) AS prev_sha
  FROM commits_export
  WHERE repo_slug = :repo_slug
) AS d
WHERE d.cycle_minutes IS NOT NULL;
 */
