"""
SQLite change-failure queries mirroring change_failure_calculator.
Keywords match change_failure_calculator for parity tests.
See docs/lake_schema_for_sqlite.md.

Python vs SQL: Month grouping uses strftime(localtime) vs datetime.fromtimestamp; typically
matches. Edge case: commit on month boundary with TZ differences could assign to different month.
"""

import sqlite3
from typing import List, Tuple

from git_calculator.work_style import SQUASH, require_known

_KEYWORDS = (
    "revert",
    "hotfix",
    "bugfix",
    "bug",
    "fix",
    "problem",
    "issue",
)


def _keyword_like_sql(expr: str) -> str:
    return " OR ".join(f"LOWER({expr}) LIKE '%{kw}%'" for kw in _KEYWORDS)


def _sql_change_failure_by_month(work_style: str) -> str:
    """
    Change-failure rate per month: % of commits with fix keywords in message.
    Keywords (match change_failure_calculator): revert, hotfix, bugfix, bug, fix, problem, issue.
    NULL message = not a fix. Rate = 100 * fix_commits / total_commits.
    squash: first line of message only (summary).
    """
    require_known(work_style)
    if work_style == SQUASH:
        subject = (
            "CASE WHEN instr(message, char(10)) > 0 "
            "THEN substr(message, 1, instr(message, char(10)) - 1) "
            "ELSE message END"
        )
        fix_pred = f"(message IS NOT NULL) AND ({_keyword_like_sql(subject)})"
    else:
        fix_pred = f"(message IS NOT NULL) AND ({_keyword_like_sql('message')})"
    return f"""
WITH by_month AS (
  SELECT
    strftime('%Y-%m', committed_date, 'unixepoch', 'localtime') AS month,
    COUNT(*) AS total_commits,
    SUM(CASE WHEN {fix_pred} THEN 1 ELSE 0 END) AS fix_commits
  FROM commits
  WHERE _raw_data_params = ?
  GROUP BY month
)
SELECT month,
  CASE WHEN total_commits = 0 THEN 0 ELSE ROUND(100.0 * fix_commits / total_commits, 1) END AS rate
FROM by_month
ORDER BY month
"""


def query_change_failure_by_month_sql(
    conn: sqlite3.Connection,
    repo_id: str,
    work_style: str = "all-branches",
) -> List[Tuple[str, float]]:
    """Return list of (month, rate) for change-failure rate. Requires commits already populated (with message)."""
    cur = conn.execute(_sql_change_failure_by_month(work_style).strip(), (repo_id,))
    return [(r[0], round(r[1], 1)) for r in cur.fetchall()]


def calculate_change_failure_rate_sql(
    conn: sqlite3.Connection,
    repo_id: str,
    work_style: str = "all-branches",
) -> List[Tuple[str, float]]:
    """
    SQL equivalent of extract_commit_data + calculate_change_failure_rate.
    Returns [(month, rate), ...] sorted by month. Requires commits populated.
    """
    return query_change_failure_by_month_sql(conn, repo_id, work_style=work_style)


def query_change_failure_chart_sql(
    conn: sqlite3.Connection,
    repo_id: str,
    work_style: str = "all-branches",
) -> List[Tuple[str, float]]:
    """
    Chart-ready change failure: (month, rate) sorted by month.
    All prepare logic in SQL for Grafana/MySQL portability.
    Requires commits already populated.
    """
    return query_change_failure_by_month_sql(conn, repo_id, work_style=work_style)
