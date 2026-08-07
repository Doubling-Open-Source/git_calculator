# SQLite schema for cycle-time (lake-compatible)

This doc defines the minimal SQLite schema used in git_calculator to mirror the DevLake lake for cycle-time validation. Full lake details: [lake_schema_gitextractor_refdiff.md](../lake_schema_gitextractor_refdiff.md). For **chart-ready aggregates** over the privacy-aware interchange, see `schema/metrics_*.sql` and `docs/adr/0002`–`0006`.

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
| log_ordinal        | INTEGER     | **Local extension:** 0-based index in `git_log()` order (newest first). Not in stock DevLake `lake.commits`. Enables `ORDER BY log_ordinal DESC` cycle-time parity with Python / `commits_export`. |

**Repo ID** (DevLake-style `local:<name>`): established at init via `SqliteLake(repo_id=None)`. If None, uses `get_repo_name()` (remote.origin.url or cwd basename).

Repo filter (same as lake): `WHERE _raw_data_params = ?` with one repo id.

## DDL (SQLite)

```sql
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT,
  message TEXT,
  log_ordinal INTEGER NOT NULL DEFAULT 0
);
```

## committed_date

Stored as **INTEGER** (Unix timestamp) so that `LAG(committed_date)` and differences are straightforward and match Python’s `commit._when`.

## log_ordinal (local extension)

Stock DevLake cannot add a sequence column without breaking lake backwards compatibility. This repo’s SqliteLake **does** store `log_ordinal` on populate so the happy-path cycle-time SQL matches git_log pairing. Legacy `ORDER BY committed_date, sha` remains available (and warns) via `query_deltas_legacy_by_committed_date`.

## Python → SQL parity (Grafana-ready)

All cycle-time data is produced by **pure SQL** in [src/calculators/sqlite_lake/](../src/calculators/sqlite_lake/). Parity tests in `tests/test_sqlite_lake_*.py` (base, cycle_time, change_failure) assert each pair returns the same results.

| Python (cycle_time_by_commits_calculator) | SQL (sqlite_lake) | Test |
|------------------------------------------|-------------------|------|
| `calculate_time_deltas(logs)` | `load_logs(logs, repo_id)` then `calculate_time_deltas_sql(repo_id)` | `test_calculate_time_deltas_parity` |
| `commit_statistics(time_deltas, bucket_size)` | `load_logs(...)` then `commit_statistics_sql(bucket_size, repo_id)` | `test_commit_statistics_parity` |
| `commit_statistics_normalized_by_month(time_deltas)` | `load_logs(...)` then `commit_statistics_normalized_by_month_sql(repo_id)` | `test_commit_statistics_normalized_by_month_parity` |
| `cycle_time_between_commits_by_author(bucket_size)` | `load_logs(...)` then `cycle_time_between_commits_by_author_sql(bucket_size, repo_id)` | `test_cycle_time_between_commits_by_author_parity` |
| `extract_commit_data` + `calculate_change_failure_rate` | `load_logs(...)` then `calculate_change_failure_rate_sql(repo_id)` | `test_change_failure_rate_parity` |

- Call `load_logs(logs, repo_id)` once to populate commits; all query methods then run pure SQL (no populate).
- **p75**: Linear interpolation in SQL. **stdev**: Sample standard deviation in SQL. Month/bucket use local time to match Python.
