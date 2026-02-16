# SQLite schema for cycle-time (lake-compatible)

This doc defines the minimal SQLite schema used in git_calculator to mirror the DevLake lake for cycle-time validation. Full lake details: [lake_schema_gitextractor_refdiff.md](../lake_schema_gitextractor_refdiff.md).

## Minimal tables

### commits

Cycle-time logic only needs: primary key, author, commit time, and repo scope.

| Column             | SQLite type | Purpose                          |
|--------------------|-------------|----------------------------------|
| sha                | TEXT        | Primary key; full commit hash    |
| author_email       | TEXT        | Author email                     |
| committed_date     | INTEGER     | Unix timestamp (seconds) for ordering and diffing |
| _raw_data_params   | TEXT        | Repo scope (e.g. `local:repo-name`) |

Repo filter (same as lake): `WHERE _raw_data_params = ?` with one repo id.

### refs (optional)

If we want the same filter pattern as the lake, a minimal table:

| Column   | SQLite type | Purpose    |
|----------|-------------|------------|
| repo_id  | TEXT        | Repo identifier (e.g. `local:git_calculator`) |

Not required for single-repo validation; useful for multi-repo or future MySQL alignment.

## DDL (SQLite)

```sql
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY,
  author_email TEXT,
  committed_date INTEGER,
  _raw_data_params TEXT
);

CREATE TABLE IF NOT EXISTS refs (
  repo_id TEXT
);
```

## committed_date

Stored as **INTEGER** (Unix timestamp) so that `LAG(committed_date)` and differences are straightforward and match Python’s `commit._when`.
