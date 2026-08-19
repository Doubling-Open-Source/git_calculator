"""
Parity: schema/metrics_author_commit_percentiles.sql vs
``commit_analyzer.extract_commits_by_author`` + ``calculate_percentiles``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import sqlite3

from git_calculator.calculators.commit_analyzer import (
    calculate_percentiles,
    extract_commits_by_author,
)

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql

AS_OF_PERIOD_FULL = "all"


def extract_author_commit_percentiles_select() -> str:
    t = read_schema_sql("metrics_author_commit_percentiles.sql")
    return extract_sql_fragment(
        t,
        "WITH totals AS (",
        "FROM totals t;",
    )


def run_author_commit_percentiles_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_author_commit_percentiles_select(),
        bind_materialization_params(repo_slug, **kwargs),
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalAuthorCommitPercentile:
    author_ref: str
    commit_count: int
    author_commit_percentile: float


def author_commit_percentiles_canonical_from_logs(
    logs: List[Any],
) -> List[CanonicalAuthorCommitPercentile]:
    cba = extract_commits_by_author(logs)
    totals = {
        author: sum(count for _, count in commits)
        for author, commits in cba.items()
    }
    pct = calculate_percentiles(cba)
    out: List[CanonicalAuthorCommitPercentile] = []
    for author in sorted(totals.keys()):
        out.append(
            CanonicalAuthorCommitPercentile(
                author,
                int(totals[author]),
                float(pct[author]),
            )
        )
    return out


def canonical_author_commit_percentiles_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalAuthorCommitPercentile]:
    out: List[CanonicalAuthorCommitPercentile] = []
    for r in rows:
        out.append(
            CanonicalAuthorCommitPercentile(
                str(r[3]),
                int(r[4]),
                float(r[5]),
            )
        )
    return sorted(out, key=lambda x: x.author_ref)


def _pct_close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)


def compare_author_commit_percentiles(
    py: Sequence[CanonicalAuthorCommitPercentile],
    sql: Sequence[CanonicalAuthorCommitPercentile],
) -> Optional[str]:
    py_m = {(x.author_ref): x for x in py}
    sql_m = {(x.author_ref): x for x in sql}
    if set(py_m) != set(sql_m):
        return (
            "author_commit_percentiles author_ref mismatch:\n"
            f"  only_py={sorted(set(py_m) - set(sql_m))[:20]}\n"
            f"  only_sql={sorted(set(sql_m) - set(py_m))[:20]}"
        )
    for a_ref in sorted(py_m):
        a, b = py_m[a_ref], sql_m[a_ref]
        if a.commit_count != b.commit_count:
            return (
                f"author_commit_percentiles mismatch {a_ref}: "
                f"py commits={a.commit_count} sql commits={b.commit_count}"
            )
        if not _pct_close(a.author_commit_percentile, b.author_commit_percentile):
            return (
                f"author_commit_percentiles mismatch {a_ref}: "
                f"py pct={a.author_commit_percentile} sql pct={b.author_commit_percentile}"
            )
    return None


def validate_author_commit_percentiles_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_author_commit_percentiles_schema_select(conn, repo_slug)
    py = author_commit_percentiles_canonical_from_logs(logs)
    sql = canonical_author_commit_percentiles_from_schema_rows(sql_rows)
    err = compare_author_commit_percentiles(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(f"authors={len(py)} as_of_period={AS_OF_PERIOD_FULL!r}")
    return None
