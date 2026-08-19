"""Keep a Changelog conversion of Changesets version headings."""

import importlib.util
from datetime import date
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "format_changelog",
    Path(__file__).resolve().parents[1] / "scripts" / "format_changelog.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_mod)


def test_converts_changesets_headings_to_keep_a_changelog():
    raw = """# Changelog

## 2.0.1

### Minor Changes

- Add a CLI flag

### Patch Changes

- Fix a crash

## [Unreleased]

## [2.0.0] - 2026-08-19

### Changed

- Old notes
"""
    out = _mod.format_text(raw, today=date(2026, 8, 19))
    assert "## [2.0.1] - 2026-08-19" in out
    assert "### Added" in out
    assert "### Fixed" in out
    assert "### Minor Changes" not in out
    assert out.index("## [Unreleased]") < out.index("## [2.0.1] - 2026-08-19")
    assert out.index("## [2.0.1] - 2026-08-19") < out.index("## [2.0.0] - 2026-08-19")
