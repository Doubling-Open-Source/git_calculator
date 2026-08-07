"""
Parity: schema/metrics_throughput_monthly.sql vs throughput_calculator (Python).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import sqlite3

from src.calculators.throughput_calculator import extract_commits_and_authors

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql


def extract_throughput_monthly_select() -> str:
    t = read_schema_sql("metrics_throughput_monthly.sql")
    return extract_sql_fragment(
        t,
        "SELECT\n  :repo_slug,\n  :dataset_id,\n  m.period_month,\n  COUNT(*) AS commit_count,",
        "GROUP BY m.period_month;",
    )


def run_throughput_monthly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_throughput_monthly_select(), bind_materialization_params(repo_slug, **kwargs)
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalThroughputMonthly:
    period_month: str
    commit_count: int
    distinct_author_count: int


def _normalize_legacy_month_key(month_key: str) -> str:
    """Legacy throughput uses 'YYYY-M'; SQL uses 'YYYY-MM'."""
    y, m = month_key.split("-", 1)
    return f"{int(y)}-{int(m):02d}"


def throughput_monthly_canonical_from_logs(logs: List[Any]) -> List[CanonicalThroughputMonthly]:
    data = extract_commits_and_authors(logs)
    out: List[CanonicalThroughputMonthly] = []
    for month, (authors, cnt) in data.items():
        out.append(
            CanonicalThroughputMonthly(
                _normalize_legacy_month_key(month), cnt, len(authors)
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def canonical_throughput_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalThroughputMonthly]:
    out: List[CanonicalThroughputMonthly] = []
    for r in rows:
        out.append(
            CanonicalThroughputMonthly(
                str(r[2]),
                int(r[3]),
                int(r[4]),
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def compare_throughput_monthly(
    py: Sequence[CanonicalThroughputMonthly],
    sql: Sequence[CanonicalThroughputMonthly],
) -> Optional[str]:
    py_m = {x.period_month: x for x in py}
    sql_m = {x.period_month: x for x in sql}
    if set(py_m) != set(sql_m):
        return "throughput period_month key mismatch:\n  only_py=%s only_sql=%s" % (
            sorted(set(py_m) - set(sql_m)),
            sorted(set(sql_m) - set(py_m)),
        )
    for m in sorted(py_m):
        a, b = py_m[m], sql_m[m]
        if a.commit_count != b.commit_count or a.distinct_author_count != b.distinct_author_count:
            return (
                f"throughput mismatch {m}: py commits={a.commit_count} authors={a.distinct_author_count} "
                f"sql commits={b.commit_count} authors={b.distinct_author_count}"
            )
    return None


def validate_throughput_monthly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_throughput_monthly_schema_select(conn, repo_slug)
    py = throughput_monthly_canonical_from_logs(logs)
    sql = canonical_throughput_from_schema_rows(sql_rows)
    err = compare_throughput_monthly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        commits = sum(x.commit_count for x in py)
        on_ok_audit(f"period_months={len(py)} commits_across_months={commits}")
    return None
