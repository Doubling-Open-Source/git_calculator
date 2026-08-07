"""Unit tests for schema_metrics_fixtures helpers."""

from __future__ import annotations

from tests.schema_metrics_fixtures import FakeCommit, message_batch_subject_body


def test_message_batch_third_element_is_full_percent_b():
    """Third tuple element must mirror git %B (subject + blank line + body), not body alone."""
    logs = [FakeCommit("a" * 40, 1.0, "e@x")]
    batch = message_batch_subject_body(logs, "fix: title", "body line")
    _s, _b, raw_b = batch[logs[0]._sha]
    assert raw_b == "fix: title\n\nbody line"
    batch_empty = message_batch_subject_body(logs, "subject only", "")
    assert batch_empty[logs[0]._sha][2] == "subject only"
