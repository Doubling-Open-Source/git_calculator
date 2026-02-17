# SQLite schema for cycle-time (lake-compatible)

This doc defines the minimal SQLite schema used in git_calculator to mirror the DevLake lake for cycle-time validation. Full lake details: [lake_schema_gitextractor_refdiff.md](../lake_schema_gitextractor_refdiff.md).

## Minimal tables

### commits

Cycle-time logic needs: primary key, author, commit time, and repo scope. Change-failure also uses `message` (same column exists in DevLake).

| Column             | SQLite type | Purpose                          |
|--------------------|-------------|----------------------------------|
| sha                | TEXT        | Primary key; full commit hash    |
| author_email       | TEXT        | Author email                     |
| committed_date     | INTEGER     | Unix timestamp (seconds) for ordering and diffing |
| _raw_data_params   | TEXT        | Repo scope (e.g. `local:repo-name`) |
| message            | TEXT        | Commit message (for change-failure; exists in DevLake) |

Repo filter (same as lake): `WHERE _raw_data_params = ?` with one repo id.

## DDL (SQLite)

```sql
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT,
  message TEXT
);
```

## committed_date

Stored as **INTEGER** (Unix timestamp) so that `LAG(committed_date)` and differences are straightforward and match Python’s `commit._when`.

## Python → SQL parity (Grafana-ready)

All cycle-time data is produced by **pure SQL** in [src/calculators/sqlite_lake/](../src/calculators/sqlite_lake/). Parity tests in `tests/test_sqlite_lake_*.py` (base, cycle_time, change_failure) assert each pair returns the same results.

| Python (cycle_time_by_commits_calculator) | SQL (sqlite_lake) | Test |
|------------------------------------------|-------------------|------|
| `calculate_time_deltas(logs)` | `calculate_time_deltas_sql(conn, logs=None)` | `test_calculate_time_deltas_parity` |
| `commit_statistics(time_deltas, bucket_size)` | `commit_statistics_sql(conn, bucket_size, logs=None)` | `test_commit_statistics_parity` |
| `commit_statistics_normalized_by_month(time_deltas)` | `commit_statistics_normalized_by_month_sql(conn, logs=None)` | `test_commit_statistics_normalized_by_month_parity` |
| `cycle_time_between_commits_by_author(bucket_size)` | `cycle_time_between_commits_by_author_sql(conn, bucket_size, logs=None)` | `test_cycle_time_between_commits_by_author_parity` |
| `extract_commit_data` + `calculate_change_failure_rate` (change_failure_calculator) | `calculate_change_failure_rate_sql(conn, logs=None)` | `test_change_failure_rate_parity` (test_sqlite_lake_change_failure_validation.py) |

- **_sql** functions populate from `logs` (or `git_log()` if `logs=None`) then run pure SQL; return shape matches the Python function.
- **p75**: Linear interpolation in SQL. **stdev**: Sample standard deviation in SQL. Month/bucket use local time to match Python.
