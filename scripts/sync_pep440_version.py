#!/usr/bin/env python3
"""Copy the Changesets package.json version into pyproject.toml (PEP 440 source of truth)."""

from __future__ import annotations

import json
import re
from pathlib import Path


def sync(package_json: Path, pyproject: Path) -> str:
    version = json.loads(package_json.read_text())["version"]
    text = pyproject.read_text()
    updated, n = re.subn(
        r'(?m)^version = "[^"]+"',
        f'version = "{version}"',
        text,
        count=1,
    )
    if n != 1:
        raise SystemExit("could not update pyproject.toml version")
    pyproject.write_text(updated)
    return version


def main() -> None:
    print(sync(Path("package.json"), Path("pyproject.toml")))


if __name__ == "__main__":
    main()
