"""
Helpers for reading ``schema/metrics_*.sql`` and binding named parameters
(``:repo_slug``, ``:dataset_id``, …) used by materialization SELECTs.

Validation modules should **not** reimplement metric math in parallel to legacy calculators:
prefer calling existing calculator helpers, then map rows to canonical dataclasses and
compare to SQL. Shared git-log pairing lives here when multiple metrics need the same order.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import sqlite3

from git_calculator.calculators.sqlite_lake.paths import SCHEMA_DIR


def git_log_author_consecutive_pairs(logs: List[Any]) -> List[Tuple[str, Any, Any]]:
    """
    (author, commits[i], commits[i+1]) in the same order as
    ``cycle_time_by_commits_calculator.calculate_time_deltas`` (git log iteration, per author).
    """
    author_map: Dict[str, List[Any]] = {}
    for commit in logs:
        author_map.setdefault(commit._author[0], []).append(commit)
    out: List[Tuple[str, Any, Any]] = []
    for _author, commits in author_map.items():
        for i in range(len(commits) - 1):
            out.append((_author, commits[i], commits[i + 1]))
    return out


def read_schema_sql(filename: str) -> str:
    """Load a file from ``schema/`` (e.g. ``metrics_throughput_monthly.sql``)."""
    return (SCHEMA_DIR / filename).read_text(encoding="utf-8")


def extract_sql_fragment(sql_text: str, start: str, end: str) -> str:
    """Return the substring from ``start`` through ``end`` (inclusive of ``end``)."""
    i = sql_text.find(start)
    j = sql_text.find(end, i)
    if i < 0 or j < 0:
        raise ValueError(f"extract failed start={start[:40]!r} end={end[:40]!r}")
    return sql_text[i : j + len(end)].strip()


def bind_materialization_params(
    repo_slug: str,
    *,
    dataset_id: str = "validation",
    source_commits_schema_version: Optional[int] = 3,
    computed_at: int = 0,
    tenant_id: Optional[str] = None,
    work_style: str = "all-branches",
) -> Dict[str, Any]:
    """Parameters for commented materialization SELECTs in ``schema/metrics_*.sql``."""
    return {
        "repo_slug": repo_slug,
        "dataset_id": dataset_id,
        "source_commits_schema_version": source_commits_schema_version,
        "computed_at": computed_at,
        "tenant_id": tenant_id,
        "work_style": work_style,
    }


def register_local_days_shift(conn: sqlite3.Connection) -> None:
    """
    SQLite helper mirroring ``datetime.fromtimestamp(ts) + timedelta(days=n)``.

    Needed for weekly lookback starts; fixed ``n*86400`` disagrees across DST.
    """

    def local_days_shift(ts: Any, days: Any) -> int:
        base = datetime.fromtimestamp(int(ts))
        return int((base + timedelta(days=int(days))).timestamp())

    conn.create_function("local_days_shift", 2, local_days_shift)
