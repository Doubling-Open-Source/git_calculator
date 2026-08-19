"""
Parity: schema/metrics_cycle_time_delta_events.sql vs ``calculate_time_deltas`` semantics.

Minutes match ``cycle_time_by_commits_calculator.calculate_time_deltas`` (local timedelta)
and the SQL ``julianday(local)`` gap — same pairing as ``time_deltas_sql_aligned_minutes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import sqlite3

from git_calculator.calculators.sqlite_lake.schema import get_full_sha

from ._common import (
    bind_materialization_params,
    extract_sql_fragment,
    git_log_author_consecutive_pairs,
    read_schema_sql,
)
from .metrics_cycle_time_monthly import time_deltas_sql_aligned_minutes

DELTA_MINUTES_TOL = 0.02


def extract_cycle_time_delta_events_select() -> str:
    t = read_schema_sql("metrics_cycle_time_delta_events.sql")
    return extract_sql_fragment(
        t,
        "SELECT\n  :repo_slug,\n  :dataset_id,\n  d.author_ref,",
        "WHERE d.cycle_minutes IS NOT NULL;",
    )


def run_cycle_time_delta_events_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_cycle_time_delta_events_select(), bind_materialization_params(repo_slug, **kwargs)
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalCycleTimeDeltaEvent:
    author_ref: str
    committed_at: int
    child_sha: str
    cycle_minutes: float
    prev_sha: Optional[str]


def cycle_time_delta_events_canonical_from_logs(logs: List[Any]) -> List[CanonicalCycleTimeDeltaEvent]:
    """Shape SQL rows from legacy deltas + pairing (no duplicate minute formula)."""
    pairs = git_log_author_consecutive_pairs(logs)
    deltas = time_deltas_sql_aligned_minutes(logs)
    if len(pairs) != len(deltas):
        raise RuntimeError(
            f"internal: pairs={len(pairs)} deltas={len(deltas)} (git log / calculate_time_deltas order)"
        )
    events: List[CanonicalCycleTimeDeltaEvent] = []
    for (author, current_commit, next_commit), row in zip(pairs, deltas):
        t1, mins = row[0], row[1]
        events.append(
            CanonicalCycleTimeDeltaEvent(
                author,
                int(t1),
                get_full_sha(current_commit),
                float(mins),
                get_full_sha(next_commit),
            )
        )
    return sorted(events, key=lambda x: (x.author_ref, x.committed_at, x.child_sha))


def canonical_delta_events_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalCycleTimeDeltaEvent]:
    out: List[CanonicalCycleTimeDeltaEvent] = []
    for r in rows:
        prev = r[6]
        out.append(
            CanonicalCycleTimeDeltaEvent(
                str(r[2]),
                int(r[3]),
                str(r[4]),
                float(r[5]),
                str(prev) if prev is not None else None,
            )
        )
    return sorted(out, key=lambda x: (x.author_ref, x.committed_at, x.child_sha))


def compare_cycle_time_delta_events(
    py: Sequence[CanonicalCycleTimeDeltaEvent],
    sql: Sequence[CanonicalCycleTimeDeltaEvent],
) -> Optional[str]:
    def sig(x: CanonicalCycleTimeDeltaEvent) -> Tuple[str, int, str]:
        return (x.author_ref, x.committed_at, x.child_sha)

    py_m = {sig(x): x for x in py}
    sql_m = {sig(x): x for x in sql}
    if set(py_m) != set(sql_m):
        op = sorted(set(py_m) - set(sql_m))[:10]
        os_ = sorted(set(sql_m) - set(py_m))[:10]
        return f"delta_events key mismatch only_py={op!s} only_sql={os_!s}"
    for k in sorted(py_m):
        a, b = py_m[k], sql_m[k]
        if a.prev_sha != b.prev_sha:
            return f"delta_events prev_sha {k}: py={a.prev_sha!r} sql={b.prev_sha!r}"
        if abs(a.cycle_minutes - b.cycle_minutes) > DELTA_MINUTES_TOL:
            return f"delta_events minutes {k}: py={a.cycle_minutes} sql={b.cycle_minutes}"
    return None


def validate_cycle_time_delta_events_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_cycle_time_delta_events_schema_select(conn, repo_slug)
    py = cycle_time_delta_events_canonical_from_logs(logs)
    sql = canonical_delta_events_from_schema_rows(sql_rows)
    err = compare_cycle_time_delta_events(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        authors = len({x.author_ref for x in py})
        on_ok_audit(f"events={len(py)} distinct_authors={authors}")
    return None
