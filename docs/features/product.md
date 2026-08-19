# Product

git-calculator derives DORA-style metrics from a Git repository on the local filesystem. It does not require GitHub or another hosting API.

Operators declare [work style](work-style.md) (`all-branches` vs `squash`) instead of choosing keyword math. A windowed SQL run also declares a [window](window-and-grain.md) (`--from` / `--to`) and a [grain](window-and-grain.md) (`weekly` or `monthly`). Schema-backed metrics live under `schema/` and `docs/adr/`; those files remain the interchange source of truth until migrated into this guide.
