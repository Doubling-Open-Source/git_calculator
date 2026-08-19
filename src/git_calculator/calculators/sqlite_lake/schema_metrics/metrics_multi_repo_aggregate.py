"""
``metrics_multi_repo_aggregate`` (ADR 0011).

Materialization stores cross-repo rollups keyed by ``batch_id`` / ``cohort_id``. Numbers match
``MultiRepoCalculator`` aggregate helpers (source of truth); this module maps those outputs to
table rows. Validation is **dict-based** (not ``commits_export`` / git logs), so this metric is
not part of ``ALL_METRICS`` / ``validate_schema_metrics_for_logs``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from git_calculator.calculators.multi_repo_calculator import MultiRepoCalculator
from git_calculator.multi_repo_manager import MultiRepoManager

from ._common import read_schema_sql

FLOAT_TOL = 1e-9

# Stable namespaced keys (value_real scalars; value_json reserved for future composites).
METRIC_CYCLE_SUM = "aggregate_cycle_time.monthly_sum"
METRIC_CYCLE_AVG = "aggregate_cycle_time.monthly_average"
METRIC_CYCLE_P75 = "aggregate_cycle_time.monthly_p75"
METRIC_CYCLE_STD = "aggregate_cycle_time.monthly_std"
METRIC_FAILURE_RATE = "aggregate_failure_rate.monthly_rate"
METRIC_ACTIVE_DEVS = "aggregate_active_developers.monthly_unique_count"
METRIC_THROUGHPUT = "aggregate_throughput.monthly_total_commits"
METRIC_TPAD_WEEKLY = "aggregate_throughput_per_active_dev.weekly_value"


def _row(
    batch_id: str,
    cohort_id: str,
    metric_name: str,
    period_key: str,
    value_real: Optional[float],
    value_json: Optional[str],
    source_schema_version: Optional[int],
    computed_at: int,
    tenant_id: Optional[str],
    metrics_schema_version: int,
) -> Tuple[Any, ...]:
    return (
        batch_id,
        cohort_id,
        metric_name,
        period_key,
        value_real,
        value_json,
        source_schema_version,
        computed_at,
        tenant_id,
        metrics_schema_version,
    )


def multi_repo_aggregate_materialization_rows(
    metrics: Dict[str, Dict[str, Any]],
    batch_id: str,
    cohort_id: str,
    *,
    source_schema_version: Optional[int] = None,
    computed_at: int = 0,
    tenant_id: Optional[str] = None,
    metrics_schema_version: int = 1,
) -> List[Tuple[Any, ...]]:
    """
    Build INSERT tuples for ``metrics_multi_repo_aggregate`` from per-repo metric dicts,
    using ``MultiRepoCalculator`` aggregation semantics.
    """
    calc = MultiRepoCalculator(MultiRepoManager())
    out: List[Tuple[Any, ...]] = []

    def add(
        metric_name: str,
        period_key: str,
        value_real: Optional[float],
        value_json: Optional[Any] = None,
    ) -> None:
        js = json.dumps(value_json, sort_keys=True) if value_json is not None else None
        out.append(
            _row(
                batch_id,
                cohort_id,
                metric_name,
                period_key,
                value_real,
                js,
                source_schema_version,
                computed_at,
                tenant_id,
                metrics_schema_version,
            )
        )

    for month, s, a, p, st in calc.aggregate_cycle_time_metrics(metrics):
        add(METRIC_CYCLE_SUM, month, float(s))
        add(METRIC_CYCLE_AVG, month, float(a))
        add(METRIC_CYCLE_P75, month, float(p))
        add(METRIC_CYCLE_STD, month, float(st))

    for month, rate in calc.aggregate_failure_rate_metrics(metrics):
        add(METRIC_FAILURE_RATE, month, float(rate))

    for month, n in calc.aggregate_active_developers_metrics(metrics):
        add(METRIC_ACTIVE_DEVS, month, float(n))

    for month, commits in calc.aggregate_throughput_metrics(metrics):
        add(METRIC_THROUGHPUT, month, float(commits))

    for week, tp in calc.aggregate_throughput_per_active_dev_metrics(metrics):
        add(METRIC_TPAD_WEEKLY, week, float(tp))

    return sorted(out, key=lambda r: (str(r[2]), str(r[3])))


def materialize_metrics_multi_repo_aggregate(
    conn: sqlite3.Connection,
    rows: Sequence[Tuple[Any, ...]],
) -> None:
    """Apply DDL (if needed) and insert materialization rows."""
    conn.executescript(read_schema_sql("metrics_multi_repo_aggregate.sql"))
    conn.executemany(
        """
        INSERT INTO metrics_multi_repo_aggregate (
            batch_id, cohort_id, metric_name, period_key,
            value_real, value_json,
            source_schema_version, computed_at, tenant_id, metrics_schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        list(rows),
    )


def read_metrics_multi_repo_aggregate_rows(
    conn: sqlite3.Connection,
    batch_id: str,
    cohort_id: str,
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        """
        SELECT batch_id, cohort_id, metric_name, period_key,
               value_real, value_json,
               source_schema_version, computed_at, tenant_id, metrics_schema_version
        FROM metrics_multi_repo_aggregate
        WHERE batch_id = ? AND cohort_id = ?
        ORDER BY metric_name, period_key
        """,
        (batch_id, cohort_id),
    )
    return list(cur.fetchall())


def _close_real(a: Optional[float], b: Optional[float]) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=FLOAT_TOL, abs_tol=FLOAT_TOL)


def compare_multi_repo_materialization_rows(
    expected: Sequence[Tuple[Any, ...]],
    actual: Sequence[Tuple[Any, ...]],
) -> Optional[str]:
    key = lambda r: (str(r[2]), str(r[3]))
    expected = sorted(expected, key=key)
    actual = sorted(actual, key=key)
    if len(expected) != len(actual):
        return (
            f"row count mismatch: expected {len(expected)}, got {len(actual)} "
            f"(expected keys sample {expected[:3]!r} …)"
        )
    for i, (e, a) in enumerate(zip(expected, actual)):
        if e[:4] != a[:4]:
            return f"row {i}: identity mismatch expected {e[:4]!r} got {a[:4]!r}"
        if not _close_real(
            e[4] if e[4] is None else float(e[4]),
            a[4] if a[4] is None else float(a[4]),
        ):
            return f"row {i}: value_real {e[4]!r} vs {a[4]!r}"
        if (e[5] or "") != (a[5] or ""):
            return f"row {i}: value_json mismatch"
        if e[6] != a[6] or e[7] != a[7] or e[8] != a[8] or e[9] != a[9]:
            return f"row {i}: lineage mismatch"
    return None


def validate_multi_repo_aggregate_for_metrics_dict(
    metrics: Dict[str, Dict[str, Any]],
    *,
    batch_id: str = "validation_batch",
    cohort_id: str = "validation_cohort",
    source_schema_version: Optional[int] = None,
    computed_at: int = 0,
    tenant_id: Optional[str] = None,
    metrics_schema_version: int = 1,
) -> Tuple[Optional[str], int]:
    """
    Build expected rows from ``MultiRepoCalculator``, materialize into an in-memory DB, read back,
    and compare. Returns ``(None, row_count)`` if OK, else ``(error_message, row_count)``.
    """
    expected = multi_repo_aggregate_materialization_rows(
        metrics,
        batch_id,
        cohort_id,
        source_schema_version=source_schema_version,
        computed_at=computed_at,
        tenant_id=tenant_id,
        metrics_schema_version=metrics_schema_version,
    )
    n_rows = len(expected)
    conn = sqlite3.connect(":memory:")
    try:
        materialize_metrics_multi_repo_aggregate(conn, expected)
        actual = read_metrics_multi_repo_aggregate_rows(conn, batch_id, cohort_id)
    finally:
        conn.close()
    err = compare_multi_repo_materialization_rows(expected, actual)
    return err, n_rows


def normalize_multi_repo_path_list(repo_paths: Sequence[str]) -> List[str]:
    """Absolute paths, ``expanduser``, first occurrence wins (no duplicate paths)."""
    out: List[str] = []
    seen: set[str] = set()
    for raw in repo_paths:
        abs_p = os.path.abspath(os.path.expanduser(raw))
        if abs_p not in seen:
            seen.add(abs_p)
            out.append(abs_p)
    return out


def collect_metrics_for_local_repo_paths(
    repo_paths: Sequence[str],
) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """
    Register each path on a ``MultiRepoManager`` and run ``MultiRepoCalculator.calculate_all_metrics``.

    Returns ``({}, err)`` if a path cannot be registered. Skips repos that yield no metrics
    (empty dict), same as ``calculate_all_metrics``.
    """
    paths = normalize_multi_repo_path_list(repo_paths)
    if not paths:
        return {}, "No repository paths after normalization."

    manager = MultiRepoManager()
    for i, abs_p in enumerate(paths):
        if not manager.add_repository(f"r{i}", abs_p):
            return {}, f"Could not add repository path: {abs_p}"

    calc = MultiRepoCalculator(manager)
    return calc.calculate_all_metrics(), None


def validate_multi_repo_aggregate_for_local_repo_paths(
    repo_paths: Sequence[str],
    *,
    batch_id: str = "validate_schema_metrics",
    cohort_id: Optional[str] = None,
    computed_at: Optional[int] = None,
    source_schema_version: Optional[int] = None,
    tenant_id: Optional[str] = None,
    metrics_schema_version: int = 1,
    on_audit: Optional[Callable[[str], None]] = None,
) -> Tuple[Optional[str], float, float, int]:
    """
    Compute per-repo metrics from local git checkouts, then run
    ``validate_multi_repo_aggregate_for_metrics_dict``. ``cohort_id`` defaults to a stable hash of
    the normalized path list.

    Returns ``(error_or_none, collect_seconds, validate_seconds, aggregate_row_count)``.
    ``on_audit`` receives human-readable detail lines (for schema validation detail logs).
    """
    paths = normalize_multi_repo_path_list(repo_paths)
    if not paths:
        return "No repository paths to aggregate.", 0.0, 0.0, 0

    if cohort_id is None:
        cohort_id = hashlib.sha256("\n".join(sorted(paths)).encode()).hexdigest()[:24]

    if computed_at is None:
        computed_at = int(time.time())

    t_collect0 = time.perf_counter()
    metrics, err = collect_metrics_for_local_repo_paths(paths)
    collect_s = time.perf_counter() - t_collect0
    if err:
        return err, collect_s, 0.0, 0
    if not metrics:
        return (
            "No per-repo metrics computed (repositories missing, not git dirs, or no commits).",
            collect_s,
            0.0,
            0,
        )

    if on_audit:
        on_audit(
            f"batch_id={batch_id!r} cohort_id={cohort_id!r} computed_at={computed_at}"
        )
        on_audit(f"repos_in_cohort={len(paths)} repos_with_metrics={len(metrics)}")
        for i, p in enumerate(paths):
            name = f"r{i}"
            m = metrics.get(name)
            if m is None:
                on_audit(f"path[{i}]={p!r} repo_key={name} (no metrics dict — skipped)")
                continue
            tc = m.get("total_commits", 0)
            ta = m.get("total_authors", 0)
            dr = m.get("date_range") or {}
            ctd = len(m.get("cycle_time_data") or [])
            frd = len(m.get("failure_rate_data") or [])
            tpd = len(m.get("throughput_per_active_dev_data") or [])
            awd = len(m.get("active_dev_weekly_data") or ())
            on_audit(
                f"path[{i}]={p!r} repo_key={name} total_commits={tc} total_authors={ta} "
                f"cycle_time_months={ctd} failure_rate_months={frd} "
                f"tpad_weeks={tpd} active_dev_weeks={awd} date_range={dr!r}"
            )

    t_val0 = time.perf_counter()
    err_m, n_rows = validate_multi_repo_aggregate_for_metrics_dict(
        metrics,
        batch_id=batch_id,
        cohort_id=cohort_id,
        source_schema_version=source_schema_version,
        computed_at=computed_at,
        tenant_id=tenant_id,
        metrics_schema_version=metrics_schema_version,
    )
    validate_s = time.perf_counter() - t_val0

    if on_audit:
        on_audit(f"aggregate_materialization_rows={n_rows}")

    return err_m, collect_s, validate_s, n_rows


def validate_multi_repo_aggregate_builtin_fixture() -> Optional[str]:
    """Fixed multi-repo dict fixture for unit tests."""
    m: Dict[str, Dict[str, Any]] = {
        "repo_a": {
            "cycle_time_data": [("2024-01", 10.0, 2.0, 30.0, 4.0)],
            "failure_rate_data": [("2024-01", 0.2)],
            "active_dev_data": [("2024-01", {"a1@x.com", "a2@x.com"}, 2)],
            "throughput_data": [("2024-01", {"a1"}, 5)],
            "throughput_per_active_dev_data": [("2024-W05", 100, 2, 50.0)],
            "active_dev_weekly_data": [
                ("2024-W05", 100, 2, {"a1@x.com", "shared@x.com"}),
            ],
        },
        "repo_b": {
            "cycle_time_data": [("2024-01", 30.0, 4.0, 50.0, 6.0)],
            "failure_rate_data": [("2024-01", 0.4)],
            "active_dev_data": [("2024-01", {"b1@x.com", "shared@x.com"}, 2)],
            "throughput_data": [("2024-01", {"b1"}, 7)],
            "throughput_per_active_dev_data": [("2024-W05", 50, 2, 25.0)],
            "active_dev_weekly_data": [
                ("2024-W05", 50, 2, {"b1@x.com", "shared@x.com"}),
            ],
        },
    }
    err, _n = validate_multi_repo_aggregate_for_metrics_dict(
        m,
        batch_id="builtin_batch",
        cohort_id="builtin_cohort",
        computed_at=1700000000,
    )
    return err
