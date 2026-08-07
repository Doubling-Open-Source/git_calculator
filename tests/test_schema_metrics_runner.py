"""API tests for ``schema_metrics.runner.validate_schema_metrics_for_logs`` (no git repo)."""

import time
from unittest.mock import patch

from src.calculators.sqlite_lake.schema_metrics import validate_schema_metrics_for_logs
from src.calculators.sqlite_lake.schema_metrics.constants import (
    ALL_METRICS,
    METRIC_ALL,
    METRIC_CYCLE_TIME_BY_BRANCHES,
    OPT_IN_METRICS,
)
from src.calculators.sqlite_lake.schema_metrics import runner as schema_metrics_runner
from tests.schema_metrics_fixtures import FakeCommit, message_batch_subject_body


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


def test_foundation_has_empty_metric_registry():
    """Batch 1: validators register in later PRs; keep ALL_METRICS / OPT_IN empty."""
    assert ALL_METRICS == ()
    assert OPT_IN_METRICS == ()
    assert METRIC_CYCLE_TIME_BY_BRANCHES == "cycle_time_by_branches"


def test_metric_all_succeeds_with_empty_pipeline():
    """METRIC_ALL with zero registered metrics still builds commits_export and returns OK."""
    t = time.mktime((2024, 6, 3, 12, 0, 0, -1, -1, -1))
    t2 = t + 86400
    logs = [
        FakeCommit("b" * 40, t2, "a@x"),
        FakeCommit("a" * 40, t, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "chore", "")
    with patch(
        "src.calculators.sqlite_lake.schema_metrics.runner.git_log_commit_messages_batch",
        return_value=batch,
    ):
        err = validate_schema_metrics_for_logs(
            logs, "local:no_edges", METRIC_ALL, sum_avg_tol=0.0, p75_std_tol=0.0
        )
    assert err is None, err
