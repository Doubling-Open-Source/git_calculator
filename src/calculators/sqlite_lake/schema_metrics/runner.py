"""
Orchestrates validation: one in-memory ``commits_export`` build, then each metric in order.

Batch 1 foundation: ``_PIPELINE`` / ``_OPT_IN_PIPELINE`` are empty; later metric PRs
register pipe functions aligned with ``constants.ALL_METRICS`` / ``OPT_IN_METRICS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

import sqlite3

from src.util.git_util import CommitMessagesBatch, git_log_commit_messages_batch

from .constants import ALL_METRICS, METRIC_ALL, OPT_IN_METRICS, RUNNABLE_METRICS

# Defaults used when no cycle_time_monthly module is registered yet.
DEFAULT_SUM_AVG_TOL = 1e-6
DEFAULT_P75_STD_TOL = 1e-6

AuditCallback = Optional[Callable[[str], None]]


@dataclass(frozen=True)
class _PipelineContext:
    logs: List[Any]
    repo_slug: str
    conn: sqlite3.Connection
    msg_batch: CommitMessagesBatch
    sum_avg_tol: float
    p75_std_tol: float


MetricPipe = Callable[[_PipelineContext, AuditCallback], Optional[str]]

# Order must match ``ALL_METRICS`` in ``constants.py`` (name pairing, not length-only).
_PIPELINE: Tuple[MetricPipe, ...] = ()
assert [fn.__name__ for fn in _PIPELINE] == [f"_pipe_{mid}" for mid in ALL_METRICS], (
    "pipeline steps out of sync with ALL_METRICS"
)

_OPT_IN_PIPELINE: dict[str, MetricPipe] = {}
assert set(_OPT_IN_PIPELINE) == set(OPT_IN_METRICS), "opt-in pipes out of sync with OPT_IN_METRICS"


def validate_schema_metrics_for_logs(
    logs: List[Any],
    repo_slug: str,
    metric: str = METRIC_ALL,
    *,
    sum_avg_tol: float = DEFAULT_SUM_AVG_TOL,
    p75_std_tol: float = DEFAULT_P75_STD_TOL,
    per_metric: Optional[Callable[[str, Optional[str]], None]] = None,
    on_metric_ok_audit: Optional[Callable[[str, str], None]] = None,
) -> Optional[str]:
    """
    Run one or all metric validations. Returns ``None`` if OK, else combined error text.

    ``METRIC_ALL`` runs ``ALL_METRICS`` only (SQL↔legacy parity). Opt-in metrics require
    an explicit metric id.

    Builds a single in-memory DB with ``commits_export`` and reuses it for every metric
    in scope. If ``per_metric`` is set, it is called after each metric with
    ``(metric_id, None)`` on success or ``(metric_id, error_text)`` on failure.

    If ``on_metric_ok_audit`` is set and a metric passes, it is called with
    ``(metric_id, audit_line)`` where ``audit_line`` is a short summary for logging.
    """
    from src.calculators.sqlite_lake.commits_export_populate import (
        create_commits_export_db,
        populate_commits_export_from_logs,
    )

    if metric == METRIC_ALL:
        want = set(ALL_METRICS)
        steps: List[Tuple[str, MetricPipe]] = list(zip(ALL_METRICS, _PIPELINE))
    else:
        want = {metric}
        unknown = want - set(RUNNABLE_METRICS)
        if unknown:
            return (
                f"Unknown metric(s): {sorted(unknown)}. "
                f"Choose from {list(RUNNABLE_METRICS)} or {METRIC_ALL!r}."
            )
        if metric in OPT_IN_METRICS:
            steps = [(metric, _OPT_IN_PIPELINE[metric])]
        else:
            steps = [(mid, run) for mid, run in zip(ALL_METRICS, _PIPELINE) if mid == metric]

    errors: List[str] = []
    msg_batch = git_log_commit_messages_batch()
    conn = create_commits_export_db()
    populate_commits_export_from_logs(
        conn, repo_slug, logs, commit_messages=msg_batch
    )

    ctx = _PipelineContext(
        logs=logs,
        repo_slug=repo_slug,
        conn=conn,
        msg_batch=msg_batch,
        sum_avg_tol=sum_avg_tol,
        p75_std_tol=p75_std_tol,
    )

    for mid, run in steps:
        if mid not in want:
            continue

        def _audit_cb(line: str, m: str = mid) -> None:
            if on_metric_ok_audit is not None:
                on_metric_ok_audit(m, line)

        audit_arg: AuditCallback = _audit_cb if on_metric_ok_audit else None
        err = run(ctx, audit_arg)
        if per_metric is not None:
            per_metric(mid, err)
        if err is not None:
            errors.append(f"[{mid}]\n{err}")

    if not errors:
        return None
    return "\n\n".join(errors)
