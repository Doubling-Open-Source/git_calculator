-- IMPLEMENTED — materialization via Python (``sqlite_lake/schema_metrics/metrics_multi_repo_aggregate.py``).
-- Cross-repo rollups match ``MultiRepoCalculator`` aggregate helpers (ADR 0011 source of truth).
-- Inputs are per-repo metric dicts (not ``commits_export``); consumers INSERT rows after joining
-- snapshots by ``batch_id`` / ``cohort_id``.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metrics_multi_repo_aggregate (
    batch_id TEXT NOT NULL,
    cohort_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    period_key TEXT NOT NULL,
    value_real REAL,
    value_json TEXT,
    source_schema_version INTEGER,
    computed_at INTEGER NOT NULL,
    tenant_id TEXT,
    metrics_schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (batch_id, cohort_id, metric_name, period_key)
);
