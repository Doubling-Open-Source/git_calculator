# ADR 0006: `metrics_author_commit_weekly`

## Status

Not yet approved.

## Context

Product and research sometimes need **longitudinal commit activity** per contributor (commits per week) for charts. Source: [`commits_export`](../../schema/commits_export.sql) ([ADR 0001](0001-minimal-commit-storage-schema.md)). Week boundaries follow **ISO Monday-based weeks**, labeled **`period_week`** = `YYYY-Www` (e.g. `2026-W15`), derived from `strftime('%G'…)` and `'%V'` in **commit local** calendar (same `localtime` convention as other metrics).

## Decision

**Table:** [`schema/metrics_author_commit_weekly.sql`](../../schema/metrics_author_commit_weekly.sql)

| Column | Role |
|--------|------|
| `repo_slug`, `dataset_id`, `period_week`, `author_ref` | Grain; PK. |
| `commit_count` | Commits in that ISO week for that author. |
| `first_committed_at`, `last_committed_at` | Min/max `committed_at` in the bucket (Unix seconds). |
| Lineage | `source_commits_schema_version`, `computed_at`, `tenant_id`, `metrics_schema_version`. |

**Index:** `(repo_slug, dataset_id, author_ref)` for time-series per author.

## Personally identifiable information (PII)

Stores **`author_ref` only** — never `author_label_pii`, email, or message text. If source `pii_protection_profile` is **`none`**, `author_ref` may equal **plaintext email** → treat as **direct PII** per ADR 0001.

### Re-identification risks (**higher sensitivity**)

This artifact is **more sensitive** than repo/month aggregates:

- **Small teams:** Sparse weeks and unique cadences map easily to individuals (**low k-anonymity**).
- **Pattern uniqueness:** Long runs of weekly counts can fingerprint a person even without names.
- **Cross-dataset linkage:** The same `author_ref` (same HMAC key and identity input) reused elsewhere enables joining series across exports.

**Mitigations (governance, not technical guarantees):** strict access control and retention; optional **cell suppression** (e.g. drop or bucket rows where `commit_count` is below a policy threshold); prefer **coarser** sharing (monthly aggregates) for broad audiences; **do not** join weekly series to **human resources (HR)**, directory, or external identity data without review.

**Relationship to pseudonymization:** HMAC does not equal anonymity. See [Pseudonyms are not anonymity guarantees (small N, k-anonymity, and aggregates)](0001-minimal-commit-storage-schema.md#pseudonyms-are-not-anonymity-guarantees-small-n-k-anonymity-and-aggregates) in ADR 0001.

**When not to publish:** Any setting where recipients could combine this with side knowledge to name contributors (e.g. public dashboards for tiny repos) without **statistical disclosure control (SDC)**.

## Source query

Commented `INSERT … SELECT` with `GROUP BY` ISO week + `author_ref` in [`schema/metrics_author_commit_weekly.sql`](../../schema/metrics_author_commit_weekly.sql).

## Computation notes

- Aligns with Monday-based weekly grouping used in [`commit_analyzer.py`](../../src/calculators/commit_analyzer.py) philosophy; label uses ISO `%G`/`%V` for stable `YYYY-Www` strings.

## References

- [ADR 0001](0001-minimal-commit-storage-schema.md).
