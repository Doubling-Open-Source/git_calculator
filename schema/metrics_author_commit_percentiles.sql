-- NOT YET IMPLEMENTED — stub DDL only (no materialization, no schema_metrics validation).
--
-- Target legacy behavior: ``commit_analyzer.calculate_percentiles`` / author-level commit
-- distribution summaries (not raw per-commit cycle time). Intended for charting “how
-- concentrated commits are across authors” from ``commits_export`` aggregates.
--
-- Exact columns TBD (e.g. repo snapshot vs monthly rollups).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_author_commit_percentiles (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    as_of_period TEXT NOT NULL,
    author_ref TEXT NOT NULL,
    commit_count INTEGER NOT NULL,
    author_commit_percentile REAL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, as_of_period, author_ref)
);
