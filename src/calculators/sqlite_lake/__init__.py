"""
SQLite schema and queries that mirror the DevLake lake.
Pure SQL for cycle-time and change-failure. Validation tests assert SQL matches Python.
See docs/lake_schema_for_sqlite.md.
Where Python and SQL can differ: docs/cycle_time_python_vs_sql_differences.md.
"""

from typing import Any, List, Optional

import sqlite3

from . import change_failure_calculator as cf
from . import cycle_time_by_commits_calculator as cycle
from . import schema


def _resolve_repo_id(conn: sqlite3.Connection, repo_id: Optional[str]) -> Optional[str]:
    """Return repo_id if set, else first repo in commits. None if lake empty."""
    if repo_id is not None:
        return repo_id
    return schema.get_first_repo_id(conn)


class SqliteLake:
    """
    SQLite lake for cycle-time and change-failure.
    Repo-agnostic: pass repo_id to load_logs and to query methods.
    Optional repo_id on queries: when None, uses first repo in DB (convenience for single-repo).
    """

    def __init__(self, path: Optional[str] = None):
        self._path = path
        self.conn: sqlite3.Connection = schema.create_db(path)

    def close(self) -> None:
        """Close the internal connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "SqliteLake":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def load_logs(self, logs: Optional[List[Any]], repo_id: str) -> int:
        """Load logs for one repo (logs=None uses git_log()). Idempotent (replaces for repo_id)."""
        return schema.populate_commits_from_log(self.conn, repo_id, logs=logs)

    def populate_commits_from_log(self, logs: Optional[List[Any]], repo_id: str) -> int:
        """Alias for load_logs."""
        return self.load_logs(logs, repo_id)

    def _repo(self, repo_id: Optional[str]) -> Optional[str]:
        rid = _resolve_repo_id(self.conn, repo_id)
        return rid

    def query_deltas(self, repo_id: Optional[str] = None) -> List[tuple]:
        rid = self._repo(repo_id)
        return cycle.query_deltas(self.conn, rid) if rid else []

    def query_fixed_bucket_stats_pure_sql(
        self, bucket_size: int, repo_id: Optional[str] = None
    ) -> List[tuple]:
        rid = self._repo(repo_id)
        return (
            cycle.query_fixed_bucket_stats_pure_sql(self.conn, bucket_size, rid)
            if rid
            else []
        )

    def query_by_month_stats_pure_sql(
        self, repo_id: Optional[str] = None
    ) -> List[tuple]:
        rid = self._repo(repo_id)
        return cycle.query_by_month_stats_pure_sql(self.conn, rid) if rid else []

    def calculate_time_deltas_sql(self, repo_id: Optional[str] = None) -> List[List]:
        """Requires load_logs() first."""
        rid = self._repo(repo_id)
        if not rid:
            return []
        rows = cycle.query_deltas(self.conn, rid)
        return [[r[0], r[1]] for r in rows]

    def commit_statistics_sql(
        self, bucket_size: int, repo_id: Optional[str] = None
    ) -> List[tuple]:
        """Requires load_logs() first."""
        rid = self._repo(repo_id)
        return (
            cycle.query_fixed_bucket_stats_pure_sql(self.conn, bucket_size, rid)
            if rid
            else []
        )

    def commit_statistics_normalized_by_month_sql(
        self, repo_id: Optional[str] = None
    ) -> List[tuple]:
        """By-month stats. Requires load_logs() first."""
        rid = self._repo(repo_id)
        return cycle.query_by_month_stats_pure_sql(self.conn, rid) if rid else []

    def cycle_time_between_commits_by_author_sql(
        self, bucket_size: int = 1000, repo_id: Optional[str] = None
    ) -> List[tuple]:
        """Requires load_logs() first."""
        rid = self._repo(repo_id)
        return (
            cycle.query_fixed_bucket_stats_pure_sql(self.conn, bucket_size, rid)
            if rid
            else []
        )

    def query_change_failure_by_month_sql(
        self, repo_id: Optional[str] = None
    ) -> List[tuple]:
        rid = self._repo(repo_id)
        return cf.query_change_failure_by_month_sql(self.conn, rid) if rid else []

    def calculate_change_failure_rate_sql(
        self, repo_id: Optional[str] = None
    ) -> List[tuple]:
        """Change failure rate by month. Requires load_logs() first."""
        rid = self._repo(repo_id)
        return cf.query_change_failure_by_month_sql(self.conn, rid) if rid else []

    def get_cycle_time_chart_data(self, repo_id: Optional[str] = None) -> List[tuple]:
        """Chart-ready cycle time: (month, p75_days, std_days). Requires load_logs() first."""
        rid = self._repo(repo_id)
        return cycle.query_cycle_time_chart_sql(self.conn, rid) if rid else []

    def get_change_failure_chart_data(
        self, repo_id: Optional[str] = None
    ) -> List[tuple]:
        """Chart-ready change failure: (month, rate). Requires load_logs() first."""
        rid = self._repo(repo_id)
        return cf.query_change_failure_chart_sql(self.conn, rid) if rid else []


# Schema exports
COMMITS_DDL = schema.COMMITS_DDL
get_full_sha = schema.get_full_sha
create_db = schema.create_db
