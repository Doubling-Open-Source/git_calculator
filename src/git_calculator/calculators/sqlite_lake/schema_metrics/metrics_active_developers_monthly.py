"""
Parity: schema/metrics_active_developers_monthly.sql vs active_developers_calculator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import sqlite3

from git_calculator.calculators.active_developers_calculator import (
    extract_authors,
    monthly_author_statistics,
)

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql


def extract_active_developers_monthly_select() -> str:
    t = read_schema_sql("metrics_active_developers_monthly.sql")
    return extract_sql_fragment(
        t,
        "SELECT\n  :repo_slug,\n  :dataset_id,\n  m.period_month,\n  COUNT(DISTINCT m.author_ref) AS unique_author_count,",
        "GROUP BY m.period_month;",
    )


def run_active_developers_monthly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_active_developers_monthly_select(),
        bind_materialization_params(repo_slug, **kwargs),
    )
    return list(cur.fetchall())


def _normalize_month_key(month_key: str) -> str:
    """Legacy uses 'YYYY-M'; SQL uses 'YYYY-MM'."""
    y, m = month_key.split("-", 1)
    return f"{int(y)}-{int(m):02d}"


@dataclass(frozen=True)
class CanonicalActiveDevelopersMonthly:
    period_month: str
    unique_author_count: int


def active_developers_monthly_canonical_from_logs(logs: List[Any]) -> List[CanonicalActiveDevelopersMonthly]:
    authors_by_month = extract_authors(logs)
    counts = monthly_author_statistics(authors_by_month)
    out: List[CanonicalActiveDevelopersMonthly] = []
    for month in sorted(counts.keys()):
        out.append(
            CanonicalActiveDevelopersMonthly(
                _normalize_month_key(month),
                int(counts[month]),
            )
        )
    return out


def canonical_active_developers_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalActiveDevelopersMonthly]:
    out: List[CanonicalActiveDevelopersMonthly] = []
    for r in rows:
        out.append(
            CanonicalActiveDevelopersMonthly(
                str(r[2]),
                int(r[3]),
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def compare_active_developers_monthly(
    py: Sequence[CanonicalActiveDevelopersMonthly],
    sql: Sequence[CanonicalActiveDevelopersMonthly],
) -> Optional[str]:
    py_m = {x.period_month: x for x in py}
    sql_m = {x.period_month: x for x in sql}
    if set(py_m) != set(sql_m):
        return (
            "active_developers_monthly period_month mismatch:\n"
            f"  only_py={sorted(set(py_m) - set(sql_m))[:20]}\n"
            f"  only_sql={sorted(set(sql_m) - set(py_m))[:20]}"
        )
    for k in sorted(py_m):
        a, b = py_m[k], sql_m[k]
        if a.unique_author_count != b.unique_author_count:
            return f"active_developers_monthly {k}: python={a.unique_author_count} schema_sql={b.unique_author_count}"
    return None


def validate_active_developers_monthly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    py = active_developers_monthly_canonical_from_logs(logs)
    sql_rows = run_active_developers_monthly_schema_select(conn, repo_slug)
    sql = canonical_active_developers_from_schema_rows(sql_rows)
    err = compare_active_developers_monthly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(f"months={len(py)}")
    return None
