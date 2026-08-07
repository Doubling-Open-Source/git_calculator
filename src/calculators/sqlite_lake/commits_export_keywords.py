"""
Export-time keyword flags for commits_export (ADR 0001), aligned with change_failure_calculator.
Subject uses Git %s; body uses %b (excludes subject line).
"""

from __future__ import annotations

# Same semantic set as change_failure_calculator.extract_commit_data (substring, lowercased).
CHANGE_FAILURE_KEYWORDS = frozenset(
    {"revert", "hotfix", "bugfix", "bug", "fix", "problem", "issue"}
)


def text_has_change_failure_keyword(text: str) -> bool:
    tl = text.lower()
    return any(kw in tl for kw in CHANGE_FAILURE_KEYWORDS)


def subject_body_keyword_flags(subject: str, body: str) -> tuple[int, int]:
    """Return (subject_has_keywords, body_has_keywords) as 0 or 1."""
    s = 1 if text_has_change_failure_keyword(subject) else 0
    b = 1 if text_has_change_failure_keyword(body) else 0
    return (s, b)
