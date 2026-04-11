-- NOT YET IMPLEMENTED — stub DDL only (no materialization, no schema_metrics validation).
--
-- Target legacy behavior: ``throughput_calculator.calculate_throughput_per_active_developer``
-- (monthly buckets, rolling ``weeks_back`` window for “active” authors, throughput =
-- commits / authors_in_intersection). Distinct from:
--   * ``metrics_throughput_monthly`` (raw commit_count + distinct_author_count only)
--   * ``metrics_throughput_per_active_developer_weekly`` (ISO week grain)
--
-- Planned PK grain: (repo_slug, dataset_id, period_month, weeks_back).
-- Source: ``commits_export`` once INSERT…SELECT is designed.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_throughput_per_active_developer_monthly (
    repo_slug TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    period_month TEXT NOT NULL,
    weeks_back INTEGER NOT NULL,
    total_commits INTEGER NOT NULL,
    active_authors_in_month INTEGER NOT NULL,
    throughput_per_active_dev REAL NOT NULL,
    source_commits_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (repo_slug, dataset_id, period_month, weeks_back)
);
