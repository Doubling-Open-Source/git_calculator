-- NOT YET IMPLEMENTED — stub DDL only (no materialization, no schema_metrics validation).
--
-- Target legacy behavior: ``throughput_calculator.calculate_active_developers_by_week``
-- (per ISO week: total commits in week, count of distinct authors active in the rolling
-- lookback window ending at that week). Distinct from:
--   * ``metrics_active_developers_monthly`` (unique authors per calendar month only)
--   * ``metrics_throughput_per_active_developer_weekly`` (throughput ratio, not raw active count series)
--
-- Planned PK grain: (repo_slug, dataset_id, period_week, weeks_back).
-- Source: ``commits_export`` once INSERT…SELECT is designed.

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
