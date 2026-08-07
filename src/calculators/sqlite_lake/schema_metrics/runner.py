"""
Orchestrates validation: one in-memory ``commits_export`` build, then each metric in order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

import sqlite3

from src.util.git_util import CommitMessagesBatch, git_log_commit_messages_batch

from .constants import ALL_METRICS, METRIC_ALL
from .metrics_active_developers_monthly import validate_active_developers_monthly_for_logs
from .metrics_active_developers_weekly import validate_active_developers_weekly_for_logs
from .metrics_author_commit_percentiles import validate_author_commit_percentiles_for_logs
from .metrics_cycle_time_by_branches import validate_cycle_time_by_branches_for_logs
from .metrics_throughput_per_active_developer_weekly import (
    validate_throughput_per_active_developer_weekly_for_logs,
)
from .metrics_throughput_per_active_developer_monthly import (
    validate_throughput_per_active_developer_monthly_for_logs,
)
from .metrics_change_failure_monthly import validate_change_failure_monthly_for_logs
from .metrics_cycle_time_delta_events import validate_cycle_time_delta_events_for_logs
from .metrics_cycle_time_monthly import (
    DEFAULT_P75_STD_TOL,
    DEFAULT_SUM_AVG_TOL,
    validate_cycle_time_monthly_for_logs,
)
from .metrics_throughput_monthly import validate_throughput_monthly_for_logs

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


def _pipe_cycle_time_monthly(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_cycle_time_monthly_for_logs(
        ctx.logs,
        ctx.repo_slug,
        sum_avg_tol=ctx.sum_avg_tol,
        p75_std_tol=ctx.p75_std_tol,
        conn=ctx.conn,
        on_ok_audit=on_ok_audit,
    )


def _pipe_change_failure_monthly(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_change_failure_monthly_for_logs(
        ctx.logs,
        ctx.repo_slug,
        ctx.conn,
        commit_messages=ctx.msg_batch,
        on_ok_audit=on_ok_audit,
    )


def _pipe_throughput_monthly(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_throughput_monthly_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_active_developers_monthly(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_active_developers_monthly_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_throughput_per_active_developer_weekly(
    ctx: _PipelineContext, on_ok_audit: AuditCallback
) -> Optional[str]:
    return validate_throughput_per_active_developer_weekly_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_active_developers_weekly(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_active_developers_weekly_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_throughput_per_active_developer_monthly(
    ctx: _PipelineContext, on_ok_audit: AuditCallback
) -> Optional[str]:
    return validate_throughput_per_active_developer_monthly_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_cycle_time_delta_events(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_cycle_time_delta_events_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_author_commit_percentiles(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_author_commit_percentiles_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


def _pipe_cycle_time_by_branches(ctx: _PipelineContext, on_ok_audit: AuditCallback) -> Optional[str]:
    return validate_cycle_time_by_branches_for_logs(
        ctx.logs, ctx.repo_slug, ctx.conn, on_ok_audit=on_ok_audit
    )


# Order must match ``ALL_METRICS`` in ``constants.py`` (name pairing, not length-only).
_PIPELINE: Tuple[MetricPipe, ...] = (
    _pipe_cycle_time_monthly,
    _pipe_change_failure_monthly,
    _pipe_throughput_monthly,
    _pipe_active_developers_monthly,
    _pipe_active_developers_weekly,
    _pipe_throughput_per_active_developer_weekly,
    _pipe_throughput_per_active_developer_monthly,
    _pipe_cycle_time_delta_events,
    _pipe_author_commit_percentiles,
    _pipe_cycle_time_by_branches,
)
assert [fn.__name__ for fn in _PIPELINE] == [f"_pipe_{mid}" for mid in ALL_METRICS], (
    "pipeline steps out of sync with ALL_METRICS"
)


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

    want = set(ALL_METRICS) if metric == METRIC_ALL else {metric}
    unknown = want - set(ALL_METRICS)
    if unknown:
        return (
            f"Unknown metric(s): {sorted(unknown)}. "
            f"Choose from {list(ALL_METRICS)} or {METRIC_ALL!r}."
        )

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

    for mid, run in zip(ALL_METRICS, _PIPELINE):
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
