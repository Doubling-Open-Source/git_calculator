"""Repository paths for ``schema/*.sql`` and other repo-root assets."""

from __future__ import annotations

from pathlib import Path


def _discover_repo_root() -> Path:
    """Walk parents until we find ``schema/`` and ``src/`` (git_calculator layout)."""
    here = Path(__file__).resolve().parent
    for d in (here, *here.parents):
        if (d / "schema").is_dir() and (d / "src").is_dir():
            return d
    raise RuntimeError(
        f"Could not find repository root (expected schema/ and src/) from {here}"
    )


REPO_ROOT = _discover_repo_root()
SCHEMA_DIR = REPO_ROOT / "schema"
