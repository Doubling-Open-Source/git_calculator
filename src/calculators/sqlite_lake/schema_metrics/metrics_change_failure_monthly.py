"""
Parity: schema/metrics_change_failure_monthly.sql vs change_failure_calculator (Python).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import sqlite3

from src.calculators.change_failure_calculator import (
    calculate_change_failure_rate,
    extract_commit_data,
)
from src.calculators.sqlite_lake.commits_export_keywords import text_has_change_failure_keyword
from src.calculators.sqlite_lake.schema import get_full_sha
from src.util.git_util import CommitMessagesBatch, git_run

from ._common import bind_materialization_params, extract_sql_fragment, read_schema_sql

RATE_TOL = 0.05


def _extract_commit_data_using_cached_messages(
    logs: List[Any],
    commit_messages: CommitMessagesBatch,
) -> Dict[str, Tuple[int, int]]:
    """
    Same aggregation as change_failure_calculator.extract_commit_data, using batched %B
    from git_log_commit_messages_batch; missing sha falls back to git_run per commit.
    """
    data_by_month: Dict[str, Tuple[int, int]] = {}
    for commit in logs:
        commit_date = datetime.fromtimestamp(commit._when)
        month_key = f"{commit_date.year}-{commit_date.month:02d}"
        total_commits, fix_commits = data_by_month.get(month_key, (0, 0))
        sha = get_full_sha(commit)
        got = commit_messages.get(sha)
        if got is not None:
            commit_message = got[2].strip().lower()
        else:
            commit_message = (
                git_run("log", "-n", "1", "--format=%B", commit).stdout.strip().lower()
            )
        if text_has_change_failure_keyword(commit_message):
            fix_commits += 1
        data_by_month[month_key] = (total_commits + 1, fix_commits)
    return data_by_month


def extract_change_failure_monthly_select() -> str:
    t = read_schema_sql("metrics_change_failure_monthly.sql")
    return extract_sql_fragment(
        t,
        "SELECT\n  :repo_slug,\n  :dataset_id,\n  m.period_month,\n  m.total_commits,\n  m.fix_like_commits,",
        ") AS m;",
    )


def run_change_failure_monthly_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_change_failure_monthly_select(), bind_materialization_params(repo_slug, **kwargs)
    )
    return list(cur.fetchall())


@dataclass(frozen=True)
class CanonicalChangeFailureMonthly:
    period_month: str
    total_commits: int
    fix_like_commits: int
    rate_percent: float


def change_failure_monthly_canonical_from_logs(
    logs: List[Any],
    *,
    commit_messages: Optional[CommitMessagesBatch] = None,
) -> List[CanonicalChangeFailureMonthly]:
    if commit_messages is not None:
        data = _extract_commit_data_using_cached_messages(logs, commit_messages)
    else:
        data = extract_commit_data(logs)
    rates = calculate_change_failure_rate(data)
    out: List[CanonicalChangeFailureMonthly] = []
    for month in sorted(data.keys()):
        total, fx = data[month]
        out.append(
            CanonicalChangeFailureMonthly(month, total, fx, float(rates[month]))
        )
    return out


def canonical_change_failure_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalChangeFailureMonthly]:
    out: List[CanonicalChangeFailureMonthly] = []
    for r in rows:
        out.append(
            CanonicalChangeFailureMonthly(
                str(r[2]),
                int(r[3]),
                int(r[4]),
                float(r[5]),
            )
        )
    return sorted(out, key=lambda x: x.period_month)


def compare_change_failure_monthly(
    py: Sequence[CanonicalChangeFailureMonthly],
    sql: Sequence[CanonicalChangeFailureMonthly],
) -> Optional[str]:
    py_m = {x.period_month: x for x in py}
    sql_m = {x.period_month: x for x in sql}
    if set(py_m) != set(sql_m):
        return "change_failure period_month key mismatch:\n  py=%s\n  sql=%s" % (
            sorted(set(py_m) - set(sql_m)),
            sorted(set(sql_m) - set(py_m)),
        )
    lines: List[str] = []
    for m in sorted(py_m):
        a, b = py_m[m], sql_m[m]
        if a.total_commits != b.total_commits:
            lines.append(f"  {m} total: py={a.total_commits} sql={b.total_commits}")
        if a.fix_like_commits != b.fix_like_commits:
            lines.append(f"  {m} fix_like: py={a.fix_like_commits} sql={b.fix_like_commits}")
        if abs(a.rate_percent - b.rate_percent) > RATE_TOL:
            lines.append(f"  {m} rate: py={a.rate_percent} sql={b.rate_percent}")
    if not lines:
        return None
    return "change_failure value mismatch:\n" + "\n".join(lines)


def validate_change_failure_monthly_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    commit_messages: Optional[CommitMessagesBatch] = None,
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    sql_rows = run_change_failure_monthly_schema_select(conn, repo_slug)
    py = change_failure_monthly_canonical_from_logs(
        logs, commit_messages=commit_messages
    )
    sql = canonical_change_failure_from_schema_rows(sql_rows)
    err = compare_change_failure_monthly(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        months = sorted(x.period_month for x in py)
        if months:
            on_ok_audit(f"period_months={len(py)} range={months[0]}..{months[-1]}")
        else:
            on_ok_audit("period_months=0")
    return None
