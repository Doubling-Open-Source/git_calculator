"""API tests for ``schema_metrics.runner.validate_schema_metrics_for_logs`` (no git repo)."""

from src.calculators.sqlite_lake.schema_metrics import validate_schema_metrics_for_logs
from src.calculators.sqlite_lake.schema_metrics.constants import ALL_METRICS
from src.calculators.sqlite_lake.schema_metrics import runner as schema_metrics_runner


def test_unknown_metric_returns_error():
    err = validate_schema_metrics_for_logs([], "local:x", "not_a_metric")
    assert err is not None
    assert "Unknown metric" in err


def test_pipeline_order_matches_all_metrics_ids():
    """Each ALL_METRICS id must pair with _pipe_<id> (not length-only)."""
    expected = [f"_pipe_{mid}" for mid in ALL_METRICS]
    actual = [fn.__name__ for fn in schema_metrics_runner._PIPELINE]
    assert actual == expected, (
        "ALL_METRICS and _PIPELINE are misaligned:\n"
        f"  ALL_METRICS={list(ALL_METRICS)}\n"
        f"  _PIPELINE={actual}"
    )
