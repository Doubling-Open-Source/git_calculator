# Schema validation run log (anonymized)

Operators validate [`schema/metrics_*.sql`](../schema/) against Python using **`scripts/validate_schema_metrics.py`** only.

Typical invocations (from git_calculator root):

```bash
./scripts/validate_schema_metrics.py
```

Uses **`local_schema_validation_repos.txt`** when it exists and lists paths (batch); otherwise validates **`$PWD`**.

```bash
./scripts/validate_schema_metrics.py /path/to/one/repo
./scripts/validate_schema_metrics.py --repos-file path/to/list.txt
./scripts/validate_schema_metrics.py --metric cycle_time_monthly --quiet
```

See [`scripts/local_schema_validation_repos.example.txt`](../scripts/local_schema_validation_repos.example.txt) for the repos file format (paths are **gitignored** when sensitive).

**Performance:** validation uses one batched `git log` per repo for commit messages (populate + legacy change-failure `%B`), not per-commit `git` calls. Cycle-time metric SQL uses `commits_export.log_ordinal` for LAG order (matches Python).

**Do not** record absolute paths to private or customer repos in this file.

| Date (UTC) | Scope | Result | Tool ref | Notes |
|------------|--------|--------|----------|--------|
| _template_ | all metrics | PASS/FAIL | e.g. git short SHA | e.g. N private clones; paths not stored |

### How to append a row

After a successful local batch (sensitive paths only on your machine):

1. Note the short git SHA of `git_calculator` you used.
2. Add one table row: date, `all` or metric name, PASS/FAIL, that SHA, and a count or vague description—**no file paths or hostnames**.
