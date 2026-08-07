"""
QA for streaming git commit-message parsing.

Proves the processor is O(record) in retained RAM — suitable as a drop-in for
N× per-commit ``git log -n 1``, without buffering an entire history in Python.
"""

from __future__ import annotations

import io
import tracemalloc
from unittest.mock import MagicMock, patch

import pytest

from src.util.git_util import (
    CommitMessagesBatchMemoryError,
    _GIT_MSG_FIELD_SEP,
    iter_commit_message_records_from_stream,
    iter_git_log_commit_messages,
)


def _sha(n: int) -> str:
    return f"{n:040x}"


def _encode_record(
    sha: str, *, subj: str = "subject line", body: str = "body\n", raw: str | None = None
) -> str:
    if raw is None:
        raw = f"{subj}\n\n{body}"
    return f"{sha}{_GIT_MSG_FIELD_SEP}{subj}{_GIT_MSG_FIELD_SEP}{body}{_GIT_MSG_FIELD_SEP}{raw}"


def _average_sized_stream(n_records: int, *, body_pad: int = 120) -> io.StringIO:
    """
    Synthetic NUL-delimited git-log payload.

    ~40 (sha) + ~12 (subj) + body_pad + ~raw ≈ a few hundred bytes / record —
    representative of typical short commit messages, not pathological megabyte bodies.
    """
    body = ("x" * body_pad) + "\n"
    parts: list[str] = []
    for i in range(n_records):
        parts.append(_encode_record(_sha(i), body=body))
        parts.append("\0")
    return io.StringIO("".join(parts))


def test_stream_peak_python_alloc_stays_in_mb_while_processing_large_volume():
    """
    Stream tens of MB of commit-message text while keeping tracemalloc peak in low MB.

    A naive ``capture_output`` + ``dict`` of the same volume would retain ~all of it.
    The stream parser must keep peak allocations far below total bytes yielded.
    """
    # 80k × ~200B ≈ 16MB of logical payload — enough to catch accidental full buffering.
    n_records = 80_000
    body_pad = 120
    stream = _average_sized_stream(n_records, body_pad=body_pad)

    # Rough lower bound on total payload size (must dwarf the allowed peak).
    sample = _encode_record(_sha(0), body=("x" * body_pad) + "\n")
    total_payload_estimate = n_records * (len(sample) + 1)
    assert total_payload_estimate > 10 * 1024 * 1024

    max_peak_bytes = 8 * 1024 * 1024  # 8 MiB peak for parser + loop locals

    tracemalloc.start()
    try:
        counted = 0
        total_body_chars = 0
        for sha, subj, body, raw in iter_commit_message_records_from_stream(
            stream, chunk_size=64 * 1024
        ):
            counted += 1
            total_body_chars += len(body)
            # Consumer keeps nothing — only running counters.
            _ = (sha, subj, raw)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert counted == n_records
    assert total_body_chars == n_records * (body_pad + 1)
    assert peak < max_peak_bytes, (
        f"peak Python alloc {peak / (1024 * 1024):.1f} MiB "
        f"exceeded {max_peak_bytes / (1024 * 1024):.0f} MiB limit "
        f"while streaming ~{total_payload_estimate / (1024 * 1024):.1f} MiB of records"
    )
    # Peak must be well below total volume (proves we did not materialize the stream).
    assert peak < total_payload_estimate / 4


def test_oversized_single_record_fails_fast_without_buffering_rest(monkeypatch):
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_MAX_RECORD_BYTES", "1024")
    huge_body = "y" * 50_000
    # First record already over limit; stream should error without needing more data.
    payload = _encode_record(_sha(1), body=huge_body) + "\0" + _encode_record(_sha(2)) + "\0"
    with pytest.raises(CommitMessagesBatchMemoryError, match="exceeded"):
        list(iter_commit_message_records_from_stream(io.StringIO(payload), chunk_size=512))


def test_iter_git_log_uses_single_popen_not_per_commit_git_run(monkeypatch):
    """Regression: one process for the walk, not N× git_run captures."""
    import src.util.git_util as git_util
    from unittest.mock import MagicMock, patch

    payload = _encode_record(_sha(1)) + "\0" + _encode_record(_sha(2)) + "\0"
    proc = MagicMock()
    proc.stdout = io.StringIO(payload)
    proc.stderr = io.StringIO("")
    proc.wait.return_value = 0

    monkeypatch.setenv("GIT_CALCULATOR_SILENCE_GIT_RUN", "1")
    with (
        patch.object(git_util, "git_run") as mock_run,
        patch.object(git_util, "sp_popen", return_value=proc) as mock_popen,
    ):
        rows = list(iter_git_log_commit_messages())

    mock_run.assert_not_called()
    mock_popen.assert_called_once()
    assert [r[0] for r in rows] == [_sha(1), _sha(2)]
