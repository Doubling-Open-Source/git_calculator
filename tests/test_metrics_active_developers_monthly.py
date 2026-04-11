"""Tests for schema_metrics.metrics_active_developers_monthly."""

from __future__ import annotations

import time

from src.calculators.sqlite_lake.schema_metrics.metrics_active_developers_monthly import (
    validate_active_developers_monthly_for_logs,
)

from tests.schema_metrics_fixtures import FakeCommit, fresh_db_with_logs, message_batch_subject_body


def test_active_developers_monthly_matches_extract_authors():
    base = time.mktime((2024, 3, 10, 12, 0, 0, -1, -1, -1))
    logs = [
        FakeCommit("0" * 40, base + 500, "a@x"),
        FakeCommit("1" * 40, base + 400, "b@x"),
        FakeCommit("2" * 40, base + 300, "a@x"),
    ]
    batch = message_batch_subject_body(logs, "s", "")
    conn = fresh_db_with_logs("local:adm", logs, batch)
    err = validate_active_developers_monthly_for_logs(logs, "local:adm", conn)
    assert err is None, err
