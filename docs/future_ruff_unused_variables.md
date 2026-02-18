# Future: Ruff and Codespell Deferred Fixes

## Problem

Ruff reports multiple violation types across the codebase. Fixing these would require a broad refactor. Codespell flags "gir" (import alias for git_ir) as a typo for "git".

## Current Mitigation

- **ruff.toml** `[lint] extend-ignore`: F841, F401, E902, E402, F821, E741
- **.codespell-ignore**: "gir" (valid alias)
- **.pre-commit-config.yaml**: codespell uses `-I .codespell-ignore`

## Ignored Ruff Rules

| Code | Meaning |
|------|---------|
| F841 | Unused variable |
| F401 | Unused import |
| E902 | No such file or directory (e.g. temp files) |
| E402 | Module level import not at top of file |
| F821 | Undefined name |
| E741 | Ambiguous variable name (e.g. `l`) |

## Future Work

When ready to address:

1. Remove rules from `ruff.toml` `extend-ignore` one at a time
2. Run `ruff check . --fix` and fix violations
3. For intentional cases, use `# noqa: CODE` sparingly
