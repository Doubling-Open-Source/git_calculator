"""
Parity: schema/metrics_throughput_per_active_developer_weekly.sql vs
``throughput_calculator.calculate_throughput_per_active_developer_by_week``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import sqlite3

from src.calculators.throughput_calculator import (
    calculate_throughput_per_active_developer_by_week,
)

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql

DEFAULT_WEEKS_BACK = 4
THROUGHPUT_TOL = 1e-9


def register_iso_week_monday_unix(conn: sqlite3.Connection) -> None:
    """SQLite UDF used by the materialization SELECT (Monday 00:00 local, unix seconds)."""

    def iso_week_monday_unix(iso_year: float, iso_week: float) -> int:
        y, w = int(iso_year), int(iso_week)
        return int(datetime.fromisocalendar(y, w, 1).timestamp())

    conn.create_function("iso_week_monday_unix", 2, iso_week_monday_unix)


def extract_throughput_per_active_developer_weekly_select() -> str:
    t = read_schema_sql("metrics_throughput_per_active_developer_weekly.sql")
    return extract_sql_fragment(
        t,
        "WITH labeled AS (",
        "ORDER BY wa.period_week;",
    )


def run_throughput_per_active_developer_weekly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    register_iso_week_monday_unix(conn)
    kw = dict(kwargs)
    weeks_back = int(kw.pop("weeks_back", DEFAULT_WEEKS_BACK))
    params: Dict[str, Any] = {
        **bind_materialization_params(repo_slug, **kw),
        "weeks_back": weeks_back,
    }
    cur = conn.execute(
        extract_throughput_per_active_developer_weekly_select(),
        params,
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalThroughputPerActiveDeveloperWeekly:
    period_week: str
    weeks_back: int
    total_commits: int
    active_authors_in_week: int
    throughput_per_active_dev: float


def throughput_per_active_developer_weekly_canonical_from_logs(
    logs: List[Any],
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
) -> List[CanonicalThroughputPerActiveDeveloperWeekly]:
    raw = calculate_throughput_per_active_developer_by_week(logs, weeks_back=weeks_back)
    out: List[CanonicalThroughputPerActiveDeveloperWeekly] = []
    for pw in sorted(raw.keys()):
        tc, aa, tp = raw[pw]
        out.append(
            CanonicalThroughputPerActiveDeveloperWeekly(
                pw,
                weeks_back,
                int(tc),
                int(aa),
                float(tp),
            )
        )
    return out


def canonical_throughput_per_active_dev_weekly_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalThroughputPerActiveDeveloperWeekly]:
    out: List[CanonicalThroughputPerActiveDeveloperWeekly] = []
    for r in rows:
        out.append(
            CanonicalThroughputPerActiveDeveloperWeekly(
                str(r[2]),
                int(r[3]),
                int(r[4]),
                int(r[5]),
                float(r[6]),
            )
        )
    return sorted(out, key=lambda x: (x.period_week, x.weeks_back))


def compare_throughput_per_active_developer_weekly(
    py: Sequence[CanonicalThroughputPerActiveDeveloperWeekly],
    sql: Sequence[CanonicalThroughputPerActiveDeveloperWeekly],
) -> Optional[str]:
    def key(
        x: CanonicalThroughputPerActiveDeveloperWeekly,
    ) -> Tuple[str, int]:
        return (x.period_week, x.weeks_back)

    py_m = {key(x): x for x in py}
    sql_m = {key(x): x for x in sql}
    if set(py_m) != set(sql_m):
        return (
            "throughput_per_active_developer_weekly key mismatch:\n"
            f"  only_py={sorted(set(py_m) - set(sql_m))[:20]}\n"
            f"  only_sql={sorted(set(sql_m) - set(py_m))[:20]}"
        )
    for k in sorted(py_m):
        a, b = py_m[k], sql_m[k]
        if (
            a.total_commits != b.total_commits
            or a.active_authors_in_week != b.active_authors_in_week
            or abs(a.throughput_per_active_dev - b.throughput_per_active_dev) > THROUGHPUT_TOL
        ):
            return f"throughput_per_active_developer_weekly mismatch {k}: py={a} sql={b}"
    return None


def validate_throughput_per_active_developer_weekly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    weeks_back: int = DEFAULT_WEEKS_BACK,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_throughput_per_active_developer_weekly_schema_select(
        conn, repo_slug, weeks_back=weeks_back
    )
    py = throughput_per_active_developer_weekly_canonical_from_logs(logs, weeks_back=weeks_back)
    sql = canonical_throughput_per_active_dev_weekly_from_schema_rows(sql_rows)
    err = compare_throughput_per_active_developer_weekly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(f"rows={len(py)} weeks_back={weeks_back}")
    return None
