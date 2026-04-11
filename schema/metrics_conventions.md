# Derived metrics — shared conventions

Interchange DDL lives under `schema/metrics_*.sql`; each implemented table has an ADR in `docs/adr/0002`–`0007` (and 0001 for commits). **Stub** DDL (no materialization yet) is listed in [README_METRICS_STUBS.md](README_METRICS_STUBS.md), with decisions in `docs/adr/0008`–`0011`.

| Convention | Choice |
|------------|--------|
| **Versioning** | `dataset_id TEXT NOT NULL` — idempotent batch or export run (UUID, content hash, or pipeline run id). Part of **PRIMARY KEY** with `repo_slug` and the period key (`period_month` or `period_week`). |
| **Repo scope** | `repo_slug` matches `commits_export.repo_slug`. |
| **Month bucket** | `period_month TEXT` as `YYYY-MM` from `strftime('%Y-%m', committed_at, 'unixepoch', 'localtime')` unless an ADR states otherwise. Aligns with treating `committed_at` as Git `%ct` (committer time, Unix seconds) and applying a **localtime** display bucket in materialization (see [ADR 0001](../docs/adr/0001-minimal-commit-storage-schema.md)). |
| **Week bucket** | `period_week` as ISO week label `YYYY-Www` from `%G` / `%V` in localtime ([ADR 0006](../docs/adr/0006-metrics-throughput-per-active-developer-weekly.md)). |
| **Lineage** | Optional `source_commits_schema_version INTEGER`, `computed_at INTEGER` (Unix), optional `tenant_id TEXT`; `metrics_schema_version INTEGER` on each metrics table (default 1). |
| **Personally identifiable information (PII)** | Repo/month aggregates: **no** `author_ref`. Author-bearing tables: **`author_ref` only** — never `author_label_pii`, never email columns. See ADR 0004 (medium); [ADR 0001 § pseudonyms vs anonymity](../docs/adr/0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates). |

**Source:** All reference `INSERT … SELECT` / CTE blocks read **only** from `commits_export` (no `commit_parent_edges` for metrics 0002–0006).
