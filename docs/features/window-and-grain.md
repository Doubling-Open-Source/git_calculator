# Window and grain

Two time concepts on a windowed SQL run. They are not interchangeable.

| Concept | Selects | Does not select |
| --- | --- | --- |
| **Window** (`--from` / `--to`) | Which commits and cycle-time samples count | How those commits are grouped into rows |
| **Grain** (`--grain weekly` or `monthly`) | How counted commits are aggregated into rows | Which commits fall inside the window |

## Contract

- Window instants are UTC. The interval is half-open: `[from, to)`.
- Omit both `--from` and `--to` to keep full-history monthly charts (no window).
- Pass one bound without the other: fail closed.
- `--grain` is `weekly` or `monthly`. Anything else fails closed.
- Default `--grain monthly` with no window keeps today’s full-history monthly charts.
- `--grain weekly` requires a window; without `--from` / `--to` it fails closed.
- A windowed run is SQL-lake only. `--backend python` with a window fails closed.
- [Work style](work-style.md) still chooses the commit set and the change-failure signal.
- Classification uses stored commit messages, not a property on the git object.
- Under `squash`, change-failure uses the [commit summary](../glossary/commit-summary.md) only.
- [Weekly](../glossary/grain.md) keys are ISO week `YYYY-Www` in UTC: `[Monday 00:00Z, next Monday 00:00Z)`.
- [Monthly](../glossary/grain.md) keys are calendar month `YYYY-MM` in UTC: `[first of month 00:00Z, first of next month 00:00Z)`.
- Every period that overlaps the window gets a row, including quiet periods.
- A quiet period reports change-failure rate as absent (`null`), not `0`.

Keyword strings themselves are unchanged.
