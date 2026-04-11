-- NOT YET IMPLEMENTED — stub DDL only (no materialization, no schema_metrics validation).
--
-- Target legacy behavior: ``cycle_time_by_branches`` (``BranchLine`` / merge-parent graph traversal,
-- dot output, branch strategies). Materialization should join ``commits_export`` with
-- ``commit_parent_edges`` and use ``refs_export`` when ref tips matter; ``repo_slug`` scopes the graph.
--
-- Planned shape TBD (e.g. branch_line id, merge_sha, strategy, …).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_cycle_time_by_branches (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    branch_line_id TEXT NOT NULL,
    strategy TEXT,
    root_sha TEXT,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, branch_line_id)
);
