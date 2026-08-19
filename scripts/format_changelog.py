#!/usr/bin/env python3
"""Rewrite the newest Changesets version block into Keep a Changelog form."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")
HEADING = re.compile(r"^## (\d+\.\d+\.\d+(?:[a-zA-Z0-9.\-]+)?)\s*$")
SECTION_MAP = {
    "### Major Changes": "### Changed",
    "### Minor Changes": "### Added",
    "### Patch Changes": "### Fixed",
}


def format_text(text: str, today: date | None = None) -> str:
    today = today or date.today()
    lines = text.splitlines()
    idx = None
    version = None
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            idx = i
            version = match.group(1)
            break
    if idx is None or version is None:
        return text if text.endswith("\n") else text + "\n"

    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    block = lines[idx:end]
    block[0] = f"## [{version}] - {today.isoformat()}"
    block = [SECTION_MAP.get(line, line) for line in block]
    new_lines = lines[:idx] + block + lines[end:]
    # Keep [Unreleased] above the newest dated release.
    unreleased = None
    for i, line in enumerate(new_lines):
        if line.strip() == "## [Unreleased]":
            unreleased = i
            break
    new_heading = f"## [{version}] - {today.isoformat()}"
    if unreleased is not None:
        heading_at = next(i for i, line in enumerate(new_lines) if line == new_heading)
        if heading_at < unreleased:
            rel_end = len(new_lines)
            for j in range(heading_at + 1, len(new_lines)):
                if new_lines[j].startswith("## "):
                    rel_end = j
                    break
            release = new_lines[heading_at:rel_end]
            without = new_lines[:heading_at] + new_lines[rel_end:]
            insert_at = next(
                i for i, line in enumerate(without) if line.strip() == "## [Unreleased]"
            )
            # skip blank lines after Unreleased
            k = insert_at + 1
            while k < len(without) and without[k].strip() == "":
                k += 1
            new_lines = without[:k] + release + without[k:]
    out = "\n".join(new_lines)
    return out if out.endswith("\n") else out + "\n"


def main() -> None:
    CHANGELOG.write_text(format_text(CHANGELOG.read_text()))


if __name__ == "__main__":
    main()
