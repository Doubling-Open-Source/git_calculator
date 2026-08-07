"""
Parity: schema/metrics_active_developers_weekly.sql vs
``throughput_calculator.calculate_active_developers_by_week``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import sqlite3

from src.calculators.throughput_calculator import calculate_active_developers_by_week

from ._common import (
    bind_materialization_params,
    extract_sql_fragment,
    read_schema_sql,
    register_local_days_shift,
)

DEFAULT_WEEKS_BACK = 4


def extract_active_developers_weekly_select() -> str:
    t = read_schema_sql("metrics_active_developers_weekly.sql")
    return extract_sql_fragment(
        t,
        "WITH labeled AS (",
        "ORDER BY r.period_week;",
    )


def run_active_developers_weekly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    kw = dict(kwargs)
    weeks_back = int(kw.pop("weeks_back", DEFAULT_WEEKS_BACK))
    params: Dict[str, Any] = {
        **bind_materialization_params(repo_slug, **kw),
        "weeks_back": weeks_back,
    }
    register_local_days_shift(conn)
    cur = conn.execute(
        extract_active_developers_weekly_select(),
        params,
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalActiveDevelopersWeekly:
    period_week: str
    weeks_back: int
    total_commits: int
    active_developer_count: int


def active_developers_weekly_canonical_from_logs(
    logs: List[Any],
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
) -> List[CanonicalActiveDevelopersWeekly]:
    raw = calculate_active_developers_by_week(logs, weeks_back=weeks_back)
    out: List[CanonicalActiveDevelopersWeekly] = []
    for pw in sorted(raw.keys()):
        tc, adc, _emails = raw[pw]
        out.append(
            CanonicalActiveDevelopersWeekly(
                pw,
                weeks_back,
                int(tc),
                int(adc),
            )
        )
    return out


def canonical_active_developers_weekly_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalActiveDevelopersWeekly]:
    out: List[CanonicalActiveDevelopersWeekly] = []
    for r in rows:
        out.append(
            CanonicalActiveDevelopersWeekly(
                str(r[2]),
                int(r[3]),
                int(r[4]),
                int(r[5]),
            )
        )
    return sorted(out, key=lambda x: (x.period_week, x.weeks_back))


def compare_active_developers_weekly(
    py: Sequence[CanonicalActiveDevelopersWeekly],
    sql: Sequence[CanonicalActiveDevelopersWeekly],
) -> Optional[str]:
    def key(x: CanonicalActiveDevelopersWeekly) -> Tuple[str, int]:
        return (x.period_week, x.weeks_back)

    py_m = {key(x): x for x in py}
    sql_m = {key(x): x for x in sql}
    if set(py_m) != set(sql_m):
        return (
            "active_developers_weekly key mismatch:\n"
            f"  only_py={sorted(set(py_m) - set(sql_m))[:20]}\n"
            f"  only_sql={sorted(set(sql_m) - set(py_m))[:20]}"
        )
    for k in sorted(py_m):
        a, b = py_m[k], sql_m[k]
        if a.total_commits != b.total_commits or a.active_developer_count != b.active_developer_count:
            return f"active_developers_weekly mismatch {k}: py={a} sql={b}"
    return None


def validate_active_developers_weekly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_active_developers_weekly_schema_select(
        conn, repo_slug, weeks_back=weeks_back
    )
    py = active_developers_weekly_canonical_from_logs(logs, weeks_back=weeks_back)
    sql = canonical_active_developers_weekly_from_schema_rows(sql_rows)
    err = compare_active_developers_weekly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(f"rows={len(py)} weeks_back={weeks_back}")
    return None
