"""API tests for ``schema_metrics.runner.validate_schema_metrics_for_logs`` (no git repo)."""

from src.calculators.sqlite_lake.schema_metrics import validate_schema_metrics_for_logs


def test_unknown_metric_returns_error():
    err = validate_schema_metrics_for_logs([], "local:x", "not_a_metric")
    assert err is not None
    assert "Unknown metric" in err
