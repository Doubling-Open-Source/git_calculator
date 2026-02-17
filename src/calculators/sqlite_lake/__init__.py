"""
SQLite schema and queries that mirror the DevLake lake.
Pure SQL for cycle-time and change-failure. Validation tests assert SQL matches Python.
See docs/lake_schema_for_sqlite.md.
Where Python and SQL can differ: docs/cycle_time_python_vs_sql_differences.md.
"""

from typing import Any, List, Optional

import sqlite3

from src.util.git_util import get_repo_id

from . import change_failure_calculator as cf
from . import cycle_time_by_commits_calculator as cycle
from . import schema


class SqliteLake:
    """
    SQLite lake for cycle-time and change-failure. Establishes repo_id at init.
    Use this class for all sqlite_lake operations.
    """

    def __init__(self, repo_id: Optional[str] = None):
        self.repo_id = repo_id if repo_id is not None else get_repo_id()

    def create_db(self, path: Optional[str] = None) -> sqlite3.Connection:
        return schema.create_db(path)

    def populate_commits_from_log(
        self,
        conn: sqlite3.Connection,
        logs: Optional[List[Any]] = None,
    ) -> int:
        return schema.populate_commits_from_log(conn, self.repo_id, logs=logs)

    def query_deltas(self, conn: sqlite3.Connection) -> List[tuple]:
        return cycle.query_deltas(conn, self.repo_id)

    def query_fixed_bucket_stats_pure_sql(
        self,
        conn: sqlite3.Connection,
        bucket_size: int,
    ) -> List[tuple]:
        return cycle.query_fixed_bucket_stats_pure_sql(conn, bucket_size, self.repo_id)

    def query_by_month_stats_pure_sql(self, conn: sqlite3.Connection) -> List[tuple]:
        return cycle.query_by_month_stats_pure_sql(conn, self.repo_id)

    def calculate_time_deltas_sql(
        self,
        conn: sqlite3.Connection,
        logs: Optional[List[Any]] = None,
    ) -> List[List]:
        return cycle.calculate_time_deltas_sql(conn, self.repo_id, logs=logs)

    def commit_statistics_sql(
        self,
        conn: sqlite3.Connection,
        bucket_size: int,
        logs: Optional[List[Any]] = None,
    ) -> List[tuple]:
        return cycle.commit_statistics_sql(conn, bucket_size, self.repo_id, logs=logs)

    def commit_statistics_normalized_by_month_sql(
        self,
        conn: sqlite3.Connection,
        logs: Optional[List[Any]] = None,
    ) -> List[tuple]:
        return cycle.commit_statistics_normalized_by_month_sql(
            conn, self.repo_id, logs=logs
        )

    def cycle_time_between_commits_by_author_sql(
        self,
        conn: sqlite3.Connection,
        bucket_size: int = 1000,
        logs: Optional[List[Any]] = None,
    ) -> List[tuple]:
        return cycle.cycle_time_between_commits_by_author_sql(
            conn, self.repo_id, bucket_size=bucket_size, logs=logs
        )

    def query_change_failure_by_month_sql(self, conn: sqlite3.Connection) -> List[tuple]:
        return cf.query_change_failure_by_month_sql(conn, self.repo_id)

    def calculate_change_failure_rate_sql(
        self,
        conn: sqlite3.Connection,
        logs: Optional[List[Any]] = None,
    ) -> List[tuple]:
        return cf.calculate_change_failure_rate_sql(conn, self.repo_id, logs=logs)


# Schema exports
COMMITS_DDL = schema.COMMITS_DDL
get_full_sha = schema.get_full_sha
create_db = schema.create_db
