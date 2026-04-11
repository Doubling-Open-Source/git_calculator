-- NOT YET IMPLEMENTED — stub DDL only (no materialization, no schema_metrics validation).
--
-- Target legacy behavior: ``multi_repo_calculator`` cross-repository rollups (e.g.
-- ``aggregate_cycle_time_metrics``, ``aggregate_failure_rate_metrics``,
-- ``aggregate_throughput_metrics``, weekly throughput composites). Implementation can read
-- per-repo interchange snapshots (``repo_slug``, ``export_id`` / ``dataset_id``) already stored;
-- ``batch_id`` / ``cohort_id`` here group which exports participate in one aggregate. Grain TBD.
--
-- See ``src/calculators/multi_repo_calculator.py`` for Python aggregation semantics.

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
