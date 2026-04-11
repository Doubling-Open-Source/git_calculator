# ADR 0001: Minimal commit storage schema (privacy-aware)

## Status

Not yet approved.

## Executive summary

This ADR defines a **denormalized SQLite/CSV-friendly** export for commit-level analytics: **caller-selectable personally identifiable information (PII) protection** (from plaintext identity through HMAC pseudonyms and optional encryption handles), **no stored full message body**, and **normalized parent edges** for SQL graph queries. Tooling must handle **identity semantics** (`pii_protection_profile` + `author_ref`), **time** (`%ct` vs `%z` / local heuristics), and **HMAC key lifecycle** for pseudonymous profiles (rotation breaks longitudinal joins unless migrated).

---

## Context

The git-calculator project derives DORA-style metrics from Git history: timestamps, contributor grouping, the **DAG** of commits (including merges), and heuristics for change-risk signals from message text. This ADR specifies a **portable interchange**—relational tables—that stores **only what is necessary** for those analyses, while treating **author email as PII** where profiles require it.

**Mapping to standard Git metadata (see [References](#references)):** exporters typically read history with `git log` (or equivalent) and map fields as follows:

| Interchange concept | Git source (normative) |
|---------------------|-------------------------|
| Commit id | Full object name; `git log --format=%H` (see [git-log pretty formats](https://git-scm.com/docs/git-log#_pretty_formats)). |
| Parent list + order | Same order as `parent` lines in a commit object and as `%P` (space-separated parents); first parent is the **first** token—merge mainline per [gitformat-commit](https://git-scm.com/docs/gitformat-commit). |
| `committed_at` | Committer date, Unix seconds: `%ct`. |
| `committer_tz_offset` | Committer local offset as formatted by `%z` (RFC 2822 style, e.g. `+0200`). |
| Author email / name for export-time logic | `%ae`, `%an` (author); note Git also records committer (`%ce`, `%cn`, `%ct`); this schema standardizes on **committer** time for `committed_at` unless a product policy documents use of `%at` instead. |
| Subject / body for **export-time** flags only | `%s` subject; `%b` body (excludes subject); `%B` entire message—used **during export** to compute `subject_has_keywords`, `body_has_keywords`, and conventional-type fields, **not** persisted as raw text here. |
| Ref tips for branch context | From `git-for-each-ref`, `git show-ref`, or similar—not as a per-commit “branch name” column. |

Branch membership is **not** a single-valued property of a commit: a commit can be reachable from many refs, and that set changes over time. Optional **`refs_export`** holds a **snapshot** of ref name → tip for replay with the DAG.

---

## Decision

1. **Primary store:** one **denormalized** table `commits_export` (one row per commit), optimized for inspection in `sqlite3`, Datasette, or CSV—not for minimal disk use.
2. **Optional second table:** `refs_export` for a **point-in-time** map of ref name → tip SHA when branch-aware replay matters.
3. **Caller-selectable PII protection:** every row records **`pii_protection_profile`**. **`author_ref`** and **`author_label_pii`** meanings depend on that profile (see [PII protection profiles](#pii-protection-profiles)).
4. **No full commit message** in the interchange: store boolean and small enum fields derived at export time (`subject_has_keywords`, `body_has_keywords`, optional `conventional_type` + **`conventional_type_scope`**).
5. **No per-commit branch lists** on `commits_export`; use `refs_export` or export-level metadata.
6. **SQL-native parent graph:** table **`commit_parent_edges`** (one row per parent link) mirrors Git parent order; it must stay consistent with **`parent_shas`** and **`parent_count`** on `commits_export`.

**DDL:** [`schema/commits_export.sql`](../../schema/commits_export.sql).

---

## Schema reference

### Table `commits_export`

| Column | Role |
|--------|------|
| `repo_slug` | Product-defined repository identifier; part of primary key with `sha`. |
| `pii_protection_profile` | **Required.** One of `none`, `pseudonym_hmac`, `pseudonym_hmac_strict`, `encrypted_identity` ([PII protection profiles](#pii-protection-profiles)). Usually constant per export. |
| `sha` | Full 40-character commit object name (hex); aligns with `%H`. |
| `parent_shas` | Space-separated parent SHAs in **Git parent order** (same as `%P` token order); `''` when `parent_count = 0`. |
| `parent_count` | Count of parents; must equal number of SHAs in `parent_shas`. `> 1` indicates a merge commit. |
| `committed_at` | Unix seconds; **committer** date, same semantics as **`%ct`**. |
| `period_week` | ISO week label **`YYYY-Www`** (naive local `datetime.fromtimestamp(committed_at).isocalendar()`), exporter-populated so weekly metrics SQL stays portable (no SQLite `strftime('%G'/'%V')` in materialization). |
| `week_monday_unix` | Unix seconds for Monday 00:00 local of that ISO week (`fromisocalendar`); same exporter pass as `period_week`. |
| `log_ordinal` | **Required** for analytics ordering: 0-based index in the exporter’s `git log` iteration order (newest commit first, same as `git_ir`); metric SQL uses `ORDER BY log_ordinal DESC` per author so LAG walks oldest→newest. |
| `committer_tz_offset` | Optional; string as produced by **`%z`** for that commit’s committer metadata. |
| `author_ref` | Identity key for analytics; format depends on `pii_protection_profile`. |
| `author_label_pii` | Optional display label; quasi-PII; must be NULL under `pseudonym_hmac_strict`. |
| `subject_has_keywords` | `0`/`1`; derived from subject line only (Git **`%s`**) at export. |
| `body_has_keywords` | `0`/`1`; derived from body (**`%b`**) at export. |
| `conventional_type` | Optional type token (e.g. Conventional Commits); NULL if absent. |
| `conventional_type_scope` | NULL iff `conventional_type` is NULL; else encodes parsing rule ([Conventional type scope](#conventional-type-scope)). |
| `schema_version` | Integer; increment when column semantics change. |
| `tenant_id` | Optional; included in HMAC input when set ([Canonical `author_ref` input](#canonical-author_ref-input-pseudonym-profiles-only)). |

**Primary key:** `(repo_slug, sha)`.

**Row invariant:** `conventional_type` and `conventional_type_scope` are both NULL or both non-NULL.

**Indexes:** `(repo_slug, committed_at)`, `(repo_slug, log_ordinal)`, `(repo_slug, author_ref)`, `(repo_slug, parent_count)`.

### Table `commit_parent_edges`

| Column | Role |
|--------|------|
| `repo_slug` | Matches `commits_export.repo_slug`. |
| `child_sha` | The commit; FK to `commits_export(repo_slug, sha)` in canonical DDL. |
| `parent_sha` | Parent object id; may be absent from `commits_export` if the snapshot is partial. |
| `parent_ord` | `0` = first parent (Git / `%P` order); `1+` = additional merge parents. |

**Primary key:** `(repo_slug, child_sha, parent_ord)`.

**Invariant:** Edge count per `(repo_slug, child_sha)` equals `parent_count` on that commit row; ordered `parent_sha` values match `parent_shas`.

**Index:** `(repo_slug, parent_sha)` for child-of-parent queries.

### PII protection profiles

| Profile | `author_ref` | `author_label_pii` | Use |
|---------|--------------|--------------------|-----|
| `none` | Normalized email (plaintext). | Optional name from **`%an`** or similar. | Trusted, restricted environments only. |
| `pseudonym_hmac` | HMAC-SHA256 per [canonical input](#canonical-author_ref-input-pseudonym-profiles-only). | Optional short label. | Default for data leaving a tight trust zone. |
| `pseudonym_hmac_strict` | Same HMAC as above. | **NULL**; display maps stay client-local. | Stronger minimization. |
| `encrypted_identity` | Opaque ciphertext or token; format owned by the product. | Per policy; often NULL. | Recoverable identity under key control. |

**Pseudonym key management:** Rotating or losing the HMAC secret without a migration (dual-write, re-export, or mapping table) **breaks** year-over-year continuity of `author_ref`. Store secrets in a KMS or vault, define rotation and audit procedures, and test recovery.

Bare **SHA-256(email)** without a secret is vulnerable to guessing; do not use as a silent substitute for HMAC.

### Conventional type scope

| Value | Meaning |
|-------|---------|
| `subject` | Type from subject (`%s`) only. |
| `body` | Type from body (`%b`) only. |
| `subject_and_body` | Type recorded only when subject and body agree on the same type; if they disagree, both `conventional_type` and `conventional_type_scope` are NULL unless a future schema adds a sentinel. |
| `subject_or_body_subject` | OR policy; winning parse on subject. |
| `subject_or_body_body` | OR policy; winning parse on body (document precedence in exporter runbooks). |

Exporters must document regexes and edge cases; this column records **which rule** was applied, not the parser code.

### Canonical `author_ref` input (pseudonym profiles only)

For `pseudonym_hmac` and `pseudonym_hmac_strict`, build a UTF-8 string with segments in **fixed order**, joined by ASCII `|`:

1. `t:{tenant_id}` if `tenant_id` is set.
2. `r:{repo_slug}` (prefer a real slug; avoid empty unless unavoidable).
3. `e:{normalized_email}` — trim; lowercase (Unicode-aware recommended).

Example: `t:acme-corp|r:my-org/my-repo|e:pat@example.com`

Then: `author_ref = HMAC-SHA256(key = exporter_secret, message = utf8_bytes(canonical_string))`, encoded as **lowercase hex** (or one documented encoding per deployment).

For `none`, set `author_ref` to the same normalized email string (no HMAC). For `encrypted_identity`, define format and rotation in product security documentation.

### Pseudonyms are not anonymity guarantees (small N, k-anonymity, and aggregates)

HMAC-based **`author_ref`** removes **direct** email from a table but does **not** by itself ensure **anonymity** in the privacy-engineering sense. Small sample sizes and sparse breakdowns re-enable **linkage** and **inference**. Casual or marketing use of “anonymous” for pseudonymous identifiers should be avoided.

1. **Rule of 30 (context).** In introductory statistics, \(N \geq 30\) is often used as a rule of thumb for normal approximations; for **privacy**, small \(N\) creates distinct risks that are **not** fixed by pseudonymization alone.

2. **K-anonymity and identifiability.** A dataset satisfies **k-anonymity** when each record is indistinguishable from at least \(k-1\) others on quasi-identifiers. When \(N\) in a subgroup is small, the effective \(k\) is low and **unique combinations** of attributes (role, week, repo, contribution pattern) become likely, enabling **linkage attacks** against `author_ref` or external data.

3. **High variance / outliers.** For small \(N\), aggregates (means, rates) are **sensitive to individual contribution**; outliers can “show through” summaries, weakening **statistical disclosure** protections even when raw email is absent.

4. **Sparse cells (tabular disclosure).** Cross-tabulations (e.g. week × team × metric) produce **cells with counts 1–3**. **Statistical disclosure control (SDC)** practice (government / health / census norms) often **suppresses** cells below thresholds (commonly 5 or 10). **Residual differencing:** if margins are known, small cells can imply exact individual values.

5. **Small population / census effect.** If the analyzed set is a large fraction of a real-world group (e.g. the whole team), the data behave like a **census**; internal knowledge maps rows to people regardless of HMAC in the file.

| Aspect | Large \(N\) (e.g. \(N \geq 30\) as a coarse band) | Small \(N\) (\(N < 30\)) |
|--------|---------------------------------------------------|-------------------------|
| Outlier influence | Diluted in aggregates | Can dominate summaries |
| Re-identification | More “crowd” to hide in | Lower k-anonymity, more unique patterns |
| Inference from patterns | Often general | May reveal individuals |
| Statistical power | Often adequate | Weak; noisy |

The “30” threshold is **pedagogical** for classical stats, not a privacy certificate. Strong guarantees often require **much larger effective \(N\)**, **suppression / aggregation**, or **differential privacy** (and policy), not pseudonymization alone.

Downstream: [ADR 0006](0006-metrics-throughput-per-active-developer-weekly.md) (weekly throughput per active developer, repo-level aggregates). Tables that expose **`author_ref`** at fine grain still assume **re-identification risk** unless k-anonymity or SDC rules are applied.

### Table `refs_export` (optional)

| Column | Role |
|--------|------|
| `repo_slug` | Same as in `commits_export`. |
| `export_id` | Groups one snapshot. |
| `ref_name` | Full ref name (e.g. `refs/heads/main`). |
| `tip_sha` | Object the ref points to. |
| `exported_at` | Unix seconds when captured. |
| `tenant_id` | Optional. |

**Primary key:** `(repo_slug, export_id, ref_name)`.

---

## Engineering tradeoffs

- **Denormalized `commits_export`:** simple audits; repeated `repo_slug` / `author_ref` acceptable when space is not the constraint.
- **`parent_shas` + `commit_parent_edges`:** redundant; edges enable joins and recursive CTEs without splitting strings; exporter must keep both in sync.
- **Graph in SQL:** bounded ancestry/descendance is practical with `WITH RECURSIVE`; hard merge-base problems may still warrant external tools—schema does not mandate a runtime.
- **`author_ref` vs `author_label_pii`:** only **`author_ref`** is the stable join key; labels are non-unique display hints.
- **Time:** `%ct` is an instant in UTC epoch seconds; `%z` (when stored) preserves committer offset for local-time heuristics.
- **No per-commit branch:** refs snapshot + DAG is the correct model.
- **Signals vs full message:** re-export from Git is required to change heuristics; bump `schema_version` and document changes.
- **`subject_has_keywords` / `body_has_keywords`:** captures subject-only vs body-only signals without storing `%B`.

---

## Consequences

- Exporters choose **`pii_protection_profile`**, populate **`author_ref`** / **`author_label_pii`** accordingly, optionally fill **`refs_export`**, and insert **`commit_parent_edges`** consistent with **`parent_shas`** / **`parent_count`**, with **`conventional_type`** / **`conventional_type_scope`** both NULL or both set.
- Consumers read **`pii_protection_profile`** before interpreting **`author_ref`**.
- Consumers treat **`committed_at`** as Git **`%ct`** semantics unless a written policy selects **`%at`** instead.
- Graph analytics should prefer **`commit_parent_edges`** over parsing **`parent_shas`** in SQL.
- HMAC rotation without migration resets pseudonymous identity in stored data; plan and test rotation.
- This repository’s calculators may remain Git-native; this interchange is optional for archives, BI, or federated metrics.

---

## References

Normative Git documentation (current editions apply):

- **[git-log](https://git-scm.com/docs/git-log)** — `git log` and **`--format`** placeholders (**`%H`**, **`%P`**, **`%T`**, **`%ct`**, **`%at`**, **`%z`**, **`%ae`**, **`%an`**, **`%ce`**, **`%cn`**, **`%s`**, **`%b`**, **`%B`**, etc.) under *Pretty formats*.
- **[gitformat-commit](https://git-scm.com/docs/gitformat-commit)** — Commit object layout; **`parent`** lines and their order (merge first parent).

Optional convention (not required by Git itself):

- **[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)** — Common grammar for type tokens when populating **`conventional_type`**.
