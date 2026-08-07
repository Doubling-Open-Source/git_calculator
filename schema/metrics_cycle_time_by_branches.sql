-- IMPLEMENTED — materialization via Python (ADR 0010); legacy ``BranchLine`` / ``cycle_time_by_branches`` is source of truth.
-- Rows mirror ``BranchLine.tree()`` nodes; ``branch_line_id`` = SHA-256 hex of ``strategy`` + ``merge_sha`` + ``root_sha`` (``root_sha`` = line entry / ``start``).
-- Reference readback (after materialization):
--
-- SELECT branch_line_id, strategy, root_sha, merge_sha, departure_sha, commit_count,
--        ramp_seconds, work_seconds, close_seconds, total_seconds
-- FROM metrics_cycle_time_by_branches
-- WHERE repo_slug = :repo_slug AND dataset_id = :dataset_id
-- ORDER BY branch_line_id;

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_cycle_time_by_branches (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    branch_line_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    root_sha TEXT NOT NULL,
    merge_sha TEXT,
    departure_sha TEXT,
    commit_count INTEGER NOT NULL,
    ramp_seconds INTEGER,
    work_seconds INTEGER,
    close_seconds INTEGER,
    total_seconds INTEGER,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, branch_line_id)
);

CREATE INDEX IF NOT EXISTS idx_metrics_ctb_repo_dataset
    ON metrics_cycle_time_by_branches (repo_slug, dataset_id);

-- Materialization: ``src/calculators/sqlite_lake/schema_metrics/metrics_cycle_time_by_branches.py`` only;
-- do not reimplement ``BranchLine`` traversal in SQL (ADR 0010).
