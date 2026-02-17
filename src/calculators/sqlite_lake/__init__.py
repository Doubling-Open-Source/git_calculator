"""
SQLite schema and queries that mirror the DevLake lake.
Pure SQL for cycle-time and change-failure. Validation tests assert SQL matches Python.
See docs/lake_schema_for_sqlite.md.
Where Python and SQL can differ: docs/cycle_time_python_vs_sql_differences.md.
"""

from . import schema
from . import cycle_time_by_commits_calculator as cycle
from . import change_failure_calculator as cf

# Schema
DEFAULT_REPO_ID = schema.DEFAULT_REPO_ID
COMMITS_DDL = schema.COMMITS_DDL
get_full_sha = schema.get_full_sha
create_db = schema.create_db
populate_commits_from_log = schema.populate_commits_from_log

# Cycle time
query_deltas = cycle.query_deltas
query_deltas_raw = cycle.query_deltas_raw
query_fixed_bucket_stats_pure_sql = cycle.query_fixed_bucket_stats_pure_sql
query_by_month_stats_pure_sql = cycle.query_by_month_stats_pure_sql
calculate_time_deltas_sql = cycle.calculate_time_deltas_sql
commit_statistics_sql = cycle.commit_statistics_sql
commit_statistics_normalized_by_month_sql = cycle.commit_statistics_normalized_by_month_sql
cycle_time_between_commits_by_author_sql = cycle.cycle_time_between_commits_by_author_sql

# Change failure
query_change_failure_by_month_sql = cf.query_change_failure_by_month_sql
calculate_change_failure_rate_sql = cf.calculate_change_failure_rate_sql
