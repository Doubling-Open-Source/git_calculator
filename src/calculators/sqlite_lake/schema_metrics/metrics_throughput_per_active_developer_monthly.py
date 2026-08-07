"""
``metrics_throughput_per_active_developer_monthly`` (ADR 0007).

Materialization and validation match legacy ``throughput_calculator.calculate_throughput_per_active_developer``
exactly. The only deliberate difference is ``period_month`` formatting: **YYYY-MM** in SQL and
canonical rows (same calendar month as legacy keys ``YYYY-M`` from ``extract_commits_and_authors``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import sqlite3

from src.calculators.throughput_calculator import calculate_throughput_per_active_developer

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql
from .metrics_throughput_monthly import _normalize_legacy_month_key

DEFAULT_WEEKS_BACK = 4
THROUGHPUT_TOL = 1e-9


def extract_throughput_per_active_developer_monthly_select() -> str:
    t = read_schema_sql("metrics_throughput_per_active_developer_monthly.sql")
    return extract_sql_fragment(
        t,
        "WITH labeled AS (",
        "ORDER BY wa.period_month;",
    )


def run_throughput_per_active_developer_monthly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    kw = dict(kwargs)
    weeks_back = int(kw.pop("weeks_back", DEFAULT_WEEKS_BACK))
    params: dict[str, Any] = {
        **bind_materialization_params(repo_slug, **kw),
        "weeks_back": weeks_back,
    }
    cur = conn.execute(
        extract_throughput_per_active_developer_monthly_select(),
        params,
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalThroughputPerActiveDeveloperMonthly:
    period_month: str
    weeks_back: int
    total_commits: int
    active_authors_in_month: int
    throughput_per_active_dev: float


def throughput_per_active_developer_monthly_canonical_from_logs(
    logs: List[Any],
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
) -> List[CanonicalThroughputPerActiveDeveloperMonthly]:
    raw = calculate_throughput_per_active_developer(logs, weeks_back=weeks_back)
    out: List[CanonicalThroughputPerActiveDeveloperMonthly] = []
    for mk in sorted(raw.keys(), key=lambda k: _normalize_legacy_month_key(k)):
        tc, aa, tp = raw[mk]
        out.append(
            CanonicalThroughputPerActiveDeveloperMonthly(
                _normalize_legacy_month_key(mk),
                weeks_back,
                int(tc),
                int(aa),
                float(tp),
            )
        )
    return out


def canonical_throughput_per_active_dev_monthly_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalThroughputPerActiveDeveloperMonthly]:
    out: List[CanonicalThroughputPerActiveDeveloperMonthly] = []
    for r in rows:
        out.append(
            CanonicalThroughputPerActiveDeveloperMonthly(
                str(r[2]),
                int(r[3]),
                int(r[4]),
                int(r[5]),
                float(r[6]),
            )
        )
    return sorted(out, key=lambda x: (x.period_month, x.weeks_back))


def compare_throughput_per_active_developer_monthly(
    py: Sequence[CanonicalThroughputPerActiveDeveloperMonthly],
    sql: Sequence[CanonicalThroughputPerActiveDeveloperMonthly],
) -> Optional[str]:
    def key(
        x: CanonicalThroughputPerActiveDeveloperMonthly,
    ) -> Tuple[str, int]:
        return (x.period_month, x.weeks_back)

    py_m = {key(x): x for x in py}
    sql_m = {key(x): x for x in sql}
    if set(py_m) != set(sql_m):
        return (
            "throughput_per_active_developer_monthly key mismatch:\n"
            f"  only_py={sorted(set(py_m) - set(sql_m))[:20]}\n"
            f"  only_sql={sorted(set(sql_m) - set(py_m))[:20]}"
        )
    for k in sorted(py_m):
        a, b = py_m[k], sql_m[k]
        if (
            a.total_commits != b.total_commits
            or a.active_authors_in_month != b.active_authors_in_month
            or abs(a.throughput_per_active_dev - b.throughput_per_active_dev) > THROUGHPUT_TOL
        ):
            return f"throughput_per_active_developer_monthly mismatch {k}: py={a} sql={b}"
    return None


def validate_throughput_per_active_developer_monthly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_throughput_per_active_developer_monthly_schema_select(
        conn, repo_slug, weeks_back=weeks_back
    )
    py = throughput_per_active_developer_monthly_canonical_from_logs(
        logs, weeks_back=weeks_back
    )
    sql = canonical_throughput_per_active_dev_monthly_from_schema_rows(sql_rows)
    err = compare_throughput_per_active_developer_monthly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(f"rows={len(py)} weeks_back={weeks_back}")
    return None
