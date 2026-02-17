# Cycle time: Python vs SQL differences – root cause and options

When comparing Python (`cycle_time_by_commits_calculator`) and SQL (`sqlite_lake`) on real repos (e.g. ***REMOVED***), **diffs appear in deltas, fixed-bucket stats, and by-month stats**. This doc explains why and what we can do **without changing the DevLake/lake table schema** (no new columns).

---

## 1. Root causes

### 1.1 Commit ordering (main cause of delta mismatches)

**Python:** Uses **git log order** per author. It never sorts by timestamp:

- Iterates `git log` once and appends each commit to `author_map[author_email]`.
- For each author, `commits` is therefore in **log order** (whatever order `git log` returned).
- Pairs consecutive commits in that order: `(commits[i], commits[i+1])` → delta = newer − older.

**SQL:** Uses **ORDER BY committed_date** (and nothing else) in the window:

- `LAG(committed_date) OVER (PARTITION BY author_email ORDER BY committed_date)`.
- When two or more commits share the **same** `committed_date` (same second), order among them is **undefined** (implementation-dependent).
- So “previous row” for LAG can differ from Python’s “previous in log order.”

**Effect:** For the same author and same set of commits, Python and SQL can pair commits differently whenever there are **duplicate timestamps**. That produces:

- Different **deltas** (e.g. one implementation gets 4308.77 min, the other 4248.77 min — a 60‑minute swap).
- Cascading differences in **fixed-bucket** and **by-month** stats (sum, average, p75, std), because the set/order of deltas feeding the aggregates changes.

So the core issue is: **SQL has no notion of “log order”** when `committed_date` ties; the lake schema only has `committed_date` (and sha, author_email, etc.), not an ordinal from the log.

### 1.2 Floating‑point and formatting

- **Float representation:** Same logical value can appear as `267518.69` vs `267518.68999999994` in CSVs, so textual diff shows noise.
- **Rounding:** Python and SQL both round to 2 decimals for deltas and to integers for p75/std; small differences in intermediate floats can still show up in later digits or in aggregates.

These are secondary; the **ordering** issue above is what creates substantive 60‑minute and aggregate differences.

---

## 2. Constraint: no schema change

We **cannot** add a column (e.g. `log_order`) to the commits table in the **DevLake/lake** database. So any fix must work with the existing schema: at most `sha`, `author_email`, `committed_date`, `_raw_data_params` (and whatever else the lake already has).

---

## 3. Possible ways forward

### Option A: Accept “equivalent up to tie-breaking” (recommended baseline)

- **Idea:** Treat Python and SQL as **equivalent** when there are no duplicate `(author_email, committed_date)` pairs; when there are ties, allow small differences.
- **Implementation:** No code change. Document that:
  - Deltas and stats may differ when multiple commits share the same second per author.
  - For dashboards/reporting, the SQL (Grafana/MySQL) path is the source of truth; Python remains the reference implementation for single-repo tooling.
- **Pros:** No schema or query changes; matches reality of the lake.  
- **Cons:** Diff on CSVs will show differences on repos with many duplicate timestamps.

### Option B: Tie-break in SQL with existing columns only

- **Idea:** Make SQL ordering deterministic when `committed_date` ties, using only existing columns (e.g. `sha`).
- **Implementation:** Change window to  
  `ORDER BY committed_date, sha`  
  (or `ORDER BY committed_date, author_email, sha` if needed). No new columns.
- **Pros:** Stable, reproducible SQL results; no schema change.  
- **Cons:** Order among ties will **not** match Python’s log order (it will be lexical by sha). So deltas for tied commits can still differ from Python, but at least SQL will be consistent and diffable across runs.

### Option C: Normalize Python to “SQL semantics” (match SQL in Python)

- **Idea:** Change the **Python** calculator to use the same ordering rule as SQL: per author, sort by `(committed_date, sha)` and then compute deltas between consecutive rows.
- **Implementation:** In `calculate_time_deltas`, for each author sort `commits` by `(commit._when, commit_sha)` before computing consecutive pairs. Then Python and SQL use the same pairing rule.
- **Pros:** Python and SQL become comparable and consistent without touching the lake.  
- **Cons:** Python no longer follows “strict git log order”; it follows “timestamp then sha” order. If product requirement is “exactly log order,” this is a semantic change.

### Option D: Pre-aggregate or expose deltas from an ETL that has order

- **Idea:** If another system (e.g. ETL or pipeline) has access to log order when writing into the lake, it could write a **derived** table (e.g. “commit_deltas”) with one row per delta. Then Grafana/SQL would query that table instead of recomputing LAG over `commits`.
- **Implementation:** Design a small “cycle_time_deltas” (or similar) table populated by a job that runs the Python logic (or equivalent with log order) and stores (repo_id, author_email, committed_date_newer, cycle_minutes, …). Dashboards query this table.
- **Pros:** Lake schema for raw `commits` stays unchanged; reporting uses a well-defined, comparable metric.  
- **Cons:** Requires pipeline/ETL work and a new table (or view) that DevLake may or may not own.

### Option E: Document and tolerate numeric differences in comparison

- **Idea:** Keep current Python and SQL as-is; document the causes above and define a **tolerance** for comparison (e.g. allow up to N minutes difference per delta when timestamps tie, or allow small aggregate drift).
- **Implementation:** In tests or comparison scripts, compare with `abs(python - sql) <= tolerance` and/or round outputs before diff (e.g. 2 decimals for floats, integers for p75/std) to avoid float noise.
- **Pros:** No schema or semantics change; still allows regression checks.  
- **Cons:** Does not remove root cause; diffs on raw CSVs will still show differences where ties exist.

---

## 4. Summary

| Cause                     | Effect                          | Mitigation (no schema change)                          |
|---------------------------|----------------------------------|--------------------------------------------------------|
| Ordering: log vs timestamp| Different pairings when ties    | B (ORDER BY committed_date, sha) and/or C (Python sort)|
| Duplicate timestamps      | Delta and aggregate mismatches   | A (accept) or D (pre-aggregate with order in ETL)     |
| Float representation      | Noisy CSV diff                  | E (round before diff / tolerance in tests)             |

**Recommendation:** Use **Option B** in SQL so Grafana/MySQL results are stable and reproducible; optionally **Option C** if we want Python and SQL to match exactly on the same data; and **Option E** in tests/comparison so we don’t rely on byte-identical CSVs. Avoid any solution that requires new columns in the DevLake commits table.
