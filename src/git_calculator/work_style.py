"""Work style: how the clone is merged (operator-facing), not keyword math."""

from __future__ import annotations

from subprocess import CalledProcessError

from git_calculator.util.git_util import git_run

ALL_BRANCHES = "all-branches"
SQUASH = "squash"
KNOWN = frozenset({ALL_BRANCHES, SQUASH})


def require_known(work_style: str) -> str:
    if work_style not in KNOWN:
        raise ValueError(f"Unknown work-style {work_style!r}")
    return work_style


def resolve_default_branch() -> str:
    """main, else master, else origin/HEAD (see docs/glossary/default-branch.md)."""
    for ref in ("main", "master"):
        try:
            git_run("rev-parse", "--verify", ref)
            return ref
        except CalledProcessError:
            continue
    try:
        pointed = git_run(
            "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"
        ).stdout.strip()
    except CalledProcessError as exc:
        raise RuntimeError(
            "Could not resolve a default branch for work-style squash"
        ) from exc
    if not pointed:
        raise RuntimeError("Could not resolve a default branch for work-style squash")
    return pointed


def log_revision_args(work_style: str) -> list[str]:
    require_known(work_style)
    if work_style == SQUASH:
        return [resolve_default_branch()]
    return ["--all", "--reflog"]
