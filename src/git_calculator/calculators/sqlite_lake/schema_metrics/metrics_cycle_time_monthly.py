"""
Parity: schema/metrics_cycle_time_monthly.sql vs Python using the same helpers as
``cycle_time_by_commits_calculator`` (no duplicated delta/month logic).

See docs/cycle_time_python_vs_sql_differences.md for export/SQL edge cases.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import sqlite3

from git_calculator.calculators.cycle_time_by_commits_calculator import (
    calculate_time_deltas,
    commit_statistics_normalized_by_month,
)
from git_calculator.calculators.sqlite_lake.paths import SCHEMA_DIR

_METRICS_CYCLE_TIME_MONTHLY_SQL = SCHEMA_DIR / "metrics_cycle_time_monthly.sql"


class _CommitIntWhen:
    """Wrap a commit so ``_when`` is ``int`` (matches ``commits_export.committed_at``)."""

    __slots__ = ("_base", "_epoch_i")

    def __init__(self, base: Any) -> None:
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_epoch_i", int(base._when))

    @property
    def _when(self) -> int:
        return object.__getattribute__(self, "_epoch_i")

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_base"), name)

# Minutes: absorbs float aggregation noise (Python vs per-row ROUND in SQL) and ±1 on p75/std.
DEFAULT_SUM_AVG_TOL = 2.0
DEFAULT_P75_STD_TOL = 2.0


@dataclass(frozen=True)
class CanonicalCycleTimeMonthly:
    period_month: str
    sum_minutes: float
    avg_minutes: float
    p75_minutes: int
    std_minutes: int


def read_metrics_cycle_time_monthly_sql() -> str:
    return _METRICS_CYCLE_TIME_MONTHLY_SQL.read_text(encoding="utf-8")


def time_deltas_sql_aligned_minutes(logs: List[Any]) -> List[List[Any]]:
    """
    ``calculate_time_deltas`` on commits with integer epochs only (export/SQL store seconds).
    """
    return calculate_time_deltas([_CommitIntWhen(c) for c in logs])


def commit_statistics_normalized_by_month_sql_localtime(time_deltas: List[List[Any]]):
    """
    Delegates to ``commit_statistics_normalized_by_month`` (legacy month buckets + aggregates).

    Kept as a separate name so call sites and schema_metrics exports stay stable; SQL
    materialization still uses ``strftime(..., 'unixepoch', 'localtime')``, which matches
    ``datetime.fromtimestamp`` for the same epoch in typical environments.
    """
    return commit_statistics_normalized_by_month(time_deltas)


def extract_cycle_time_monthly_materialization_select(sql_text: Optional[str] = None) -> str:
    """Return the WITH...SELECT from the commented reference block in metrics_cycle_time_monthly.sql."""
    text = sql_text if sql_text is not None else read_metrics_cycle_time_monthly_sql()
    key = "WITH ordered AS ("
    start = text.find(key)
    if start < 0:
        raise ValueError(f"expected {key!r} in metrics_cycle_time_monthly.sql")
    end_marker = "ORDER BY b.month_year;"
    end = text.find(end_marker, start)
    if end < 0:
        raise ValueError(f"expected {end_marker!r} in metrics_cycle_time_monthly.sql")
    end += len(end_marker)
    return text[start:end].strip()


def run_cycle_time_monthly_schema_select(
    conn: sqlite3.Connection,
    repo_slug: str,
    *,
    dataset_id: str = "validation",
    source_commits_schema_version: Optional[int] = 1,
    computed_at: int = 0,
    tenant_id: Optional[str] = None,
) -> List[Tuple[Any, ...]]:
    sql = extract_cycle_time_monthly_materialization_select()
    params: Dict[str, Any] = {
        "repo_slug": repo_slug,
        "dataset_id": dataset_id,
        "source_commits_schema_version": source_commits_schema_version,
        "computed_at": computed_at,
        "tenant_id": tenant_id,
    }
    cur = conn.execute(sql, params)
    return list(cur.fetchall())


def canonical_from_python_by_month(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalCycleTimeMonthly]:
    """Map commit_statistics_normalized_by_month tuples (month, sum, avg, p75, std)."""
    out: List[CanonicalCycleTimeMonthly] = []
    for r in rows:
        month, s_sum, s_avg, s_p75, s_std = r[0], r[1], r[2], r[3], r[4]
        out.append(
            CanonicalCycleTimeMonthly(
                period_month=str(month),
                sum_minutes=float(s_sum),
                avg_minutes=float(s_avg),
                p75_minutes=int(s_p75),
                std_minutes=int(s_std),
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def canonical_from_schema_cycle_time_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalCycleTimeMonthly]:
    """
    Map materialization SELECT row order:
      repo_slug, dataset_id, period_month, sample_count, sum, avg, p75, std,
      source_ver, computed_at, tenant_id
    """
    out: List[CanonicalCycleTimeMonthly] = []
    for r in rows:
        out.append(
            CanonicalCycleTimeMonthly(
                period_month=str(r[2]),
                sum_minutes=float(r[4]),
                avg_minutes=float(r[5]),
                p75_minutes=int(r[6]),
                std_minutes=int(r[7]),
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def compare_canonical_cycle_time_monthly(
    py: Sequence[CanonicalCycleTimeMonthly],
    sql: Sequence[CanonicalCycleTimeMonthly],
    *,
    sum_avg_tol: float = DEFAULT_SUM_AVG_TOL,
    p75_std_tol: float = DEFAULT_P75_STD_TOL,
) -> Optional[str]:
    """
    Row-set parity then per-field numeric check. Returns None if OK, else a human-readable error.
    """
    py_m = {x.period_month: x for x in py}
    sql_m = {x.period_month: x for x in sql}
    py_keys = set(py_m)
    sql_keys = set(sql_m)
    if py_keys != sql_keys:
        only_py = sorted(py_keys - sql_keys)
        only_sql = sorted(sql_keys - py_keys)
        parts = ["period_month key mismatch."]
        if only_py:
            parts.append(f"  only Python: {only_py}")
        if only_sql:
            parts.append(f"  only schema SQL: {only_sql}")
        parts.append(
            "  (Check duplicate (author,timestamp) ordering, TZ month boundaries, "
            "and that both paths use the same git log.)"
        )
        return "\n".join(parts)

    lines: List[str] = []
    for month in sorted(py_keys):
        a, b = py_m[month], sql_m[month]
        if abs(a.sum_minutes - b.sum_minutes) > sum_avg_tol:
            lines.append(
                f"  {month} sum_minutes: python={a.sum_minutes} schema_sql={b.sum_minutes}"
            )
        if abs(a.avg_minutes - b.avg_minutes) > sum_avg_tol:
            lines.append(
                f"  {month} avg_minutes: python={a.avg_minutes} schema_sql={b.avg_minutes}"
            )
        if abs(a.p75_minutes - b.p75_minutes) > p75_std_tol:
            lines.append(
                f"  {month} p75_minutes: python={a.p75_minutes} schema_sql={b.p75_minutes}"
            )
        if abs(a.std_minutes - b.std_minutes) > p75_std_tol:
            lines.append(
                f"  {month} std_minutes: python={a.std_minutes} schema_sql={b.std_minutes}"
            )

    if not lines:
        return None
    return "Value mismatch:\n" + "\n".join(lines[:50]) + (
        "\n  ..." if len(lines) > 50 else ""
    )


CANONICAL_CSV_FIELDS = (
    "period_month",
    "sum_minutes",
    "avg_minutes",
    "p75_minutes",
    "std_minutes",
)


def write_canonical_cycle_time_csv(
    path: Path,
    rows: Sequence[CanonicalCycleTimeMonthly],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_CSV_FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x.period_month):
            w.writerow(
                {
                    "period_month": r.period_month,
                    "sum_minutes": r.sum_minutes,
                    "avg_minutes": r.avg_minutes,
                    "p75_minutes": r.p75_minutes,
                    "std_minutes": r.std_minutes,
                }
            )


def validation_failure_footer() -> str:
    return (
        "\nIf mismatches persist, see docs/cycle_time_python_vs_sql_differences.md "
        "(month TZ edges vs strftime; lake commits table ordering)."
    )


def cycle_time_monthly_canonical_pair_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Tuple[List[CanonicalCycleTimeMonthly], List[CanonicalCycleTimeMonthly]]:
    """Build canonical rows from Python and from schema SQL (same logs, same repo_slug)."""
    from git_calculator.calculators.sqlite_lake.commits_export_populate import (
        create_commits_export_db,
        populate_commits_export_from_logs,
    )

    py_rows = commit_statistics_normalized_by_month_sql_localtime(
        time_deltas_sql_aligned_minutes(logs)
    )
    own_conn = conn is None
    if own_conn:
        conn = create_commits_export_db()
        populate_commits_export_from_logs(conn, repo_slug, logs)
    sql_rows = run_cycle_time_monthly_schema_select(conn, repo_slug)
    return (
        canonical_from_python_by_month(py_rows),
        canonical_from_schema_cycle_time_rows(sql_rows),
    )


def validate_cycle_time_monthly_for_logs(
    logs: List[Any],
    repo_slug: str,
    *,
    sum_avg_tol: float = DEFAULT_SUM_AVG_TOL,
    p75_std_tol: float = DEFAULT_P75_STD_TOL,
    conn: Optional[sqlite3.Connection] = None,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """
    End-to-end: Python by-month stats vs schema/metrics_cycle_time_monthly.sql on commits_export
    populated from the same logs. Returns None if OK, else error text (without footer).
    If conn is provided, it must already contain commits_export rows for repo_slug.
    If on_ok_audit is set and validation passes, it is called once with a short audit line.
    """
    left, right = cycle_time_monthly_canonical_pair_for_logs(logs, repo_slug, conn=conn)
    err = compare_canonical_cycle_time_monthly(
        left,
        right,
        sum_avg_tol=sum_avg_tol,
        p75_std_tol=p75_std_tol,
    )
    if err is not None:
        return err
    if on_ok_audit is not None:
        if left:
            months = [x.period_month for x in sorted(left, key=lambda x: x.period_month)]
            on_ok_audit(f"period_months={len(left)} range={months[0]}..{months[-1]}")
        else:
            on_ok_audit("period_months=0 (no month with >=2 deltas)")
    return None
