"""Streaming + memory bounds for git_log_commit_messages_batch."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from src.util import git_util
from src.util.git_util import (
    CommitMessagesBatchMemoryError,
    _GIT_MSG_FIELD_SEP,
    git_log_commit_messages_batch,
)


def _record(sha: str, subj: str = "s", body: str = "b", raw: str = "B") -> str:
    return f"{sha}{_GIT_MSG_FIELD_SEP}{subj}{_GIT_MSG_FIELD_SEP}{body}{_GIT_MSG_FIELD_SEP}{raw}"


def _sha(n: int) -> str:
    return f"{n:040x}"


def _fake_popen(stdout_text: str):
    proc = MagicMock()
    proc.stdout = io.StringIO(stdout_text)
    proc.wait.return_value = 0
    proc.returncode = 0
    return proc


def test_batch_streams_without_git_run_capture():
    """Must stream via Popen, not git_run(capture_output=True) which buffers all stdout."""
    payload = _record(_sha(1)) + "\0" + _record(_sha(2)) + "\0"
    with (
        patch.object(git_util, "git_run") as mock_run,
        patch("src.util.git_util.sp_popen", return_value=_fake_popen(payload)) as mock_popen,
        patch.dict("os.environ", {"GIT_CALCULATOR_SILENCE_GIT_RUN": "1"}, clear=False),
    ):
        out = git_log_commit_messages_batch()
    mock_run.assert_not_called()
    mock_popen.assert_called_once()
    assert set(out) == {_sha(1), _sha(2)}
    assert out[_sha(1)] == ("s", "b", "B")


def test_batch_raises_when_entry_limit_exceeded(monkeypatch):
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES", "1")
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES", "0")  # unlimited bytes
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES", "0")
    payload = _record(_sha(1)) + "\0" + _record(_sha(2)) + "\0"
    with patch("src.util.git_util.sp_popen", return_value=_fake_popen(payload)):
        with pytest.raises(CommitMessagesBatchMemoryError, match="max entries"):
            git_log_commit_messages_batch()


def test_batch_raises_when_total_bytes_exceeded(monkeypatch):
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES", "0")
    # One record ~100B; allow the first, fail when the second pushes past 150.
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES", "150")
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES", "0")
    payload = (
        _record(_sha(1), subj="x" * 20, body="y" * 20, raw="z" * 20)
        + "\0"
        + _record(_sha(2), subj="x" * 20, body="y" * 20, raw="z" * 20)
        + "\0"
    )
    with patch("src.util.git_util.sp_popen", return_value=_fake_popen(payload)):
        with pytest.raises(CommitMessagesBatchMemoryError, match="max bytes"):
            git_log_commit_messages_batch()


def test_batch_raises_when_single_record_exceeds_cap(monkeypatch):
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES", "0")
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES", "0")
    monkeypatch.setenv("GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES", "50")
    huge = _record(_sha(1), subj="s", body="b" * 200, raw="B" * 200) + "\0"
    with patch("src.util.git_util.sp_popen", return_value=_fake_popen(huge)):
        with pytest.raises(CommitMessagesBatchMemoryError, match="max record"):
            git_log_commit_messages_batch()
