"""
Git process helpers.

Backwards compatibility: existing entry points keep stable signatures and behavior:
  ``get_repo_name``, ``get_repo_id``, ``git_run``.

Additive-only policy for this module: new public names may be added; do not remove
or narrow existing APIs without a deprecation path. Batch helpers live in the
``# -- additive (batched commit messages) --`` section below.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from subprocess import PIPE
from subprocess import Popen as sp_popen
from subprocess import run as sp_run
from typing import TextIO

# sha -> (subject %s, body %b, full_message %B)
CommitMessagesBatch = dict[str, tuple[str, str, str]]
# One streamed record from git log -z.
CommitMessageRecord = tuple[str, str, str, str]  # sha, subject, body, raw %B


class CommitMessagesBatchMemoryError(RuntimeError):
    """Raised when the streaming parser would retain more than configured limits."""


def get_repo_name():
    """
    Get the repository name from git configuration.
    Returns the repository name or 'repo' if not found.
    """
    try:
        remote_url = git_run("config", "--get", "remote.origin.url").stdout.strip()
        if remote_url:
            repo_name = os.path.basename(remote_url)
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            return repo_name
    except Exception:
        pass

    try:
        return os.path.basename(os.getcwd())
    except Exception:
        return "repo"


def get_repo_id():
    """DevLake-style repo_id: local:<repo_name>."""
    return f"local:{get_repo_name()}"


def git_run(*args):
    """
    Execute a Git command with its arguments, print the command for reference,
    run it using a subprocess, capture its output, and return the result.

    This function allows you to interact with Git from within a Python script
    and access the results of Git commands programmatically.

    Args:
        *args: A variable number of arguments representing the Git command
               and its options and arguments.

    Returns:
        CompletedProcess: An object containing information about the executed
        command, including its return code, standard output, and standard error.
    """
    if os.environ.get("GIT_CALCULATOR_SILENCE_GIT_RUN") != "1":
        print("# $> git", *args)
    res = sp_run(["git"] + list(args), check=True, text=True, capture_output=True)
    return res


# -- additive (batched commit messages) --

# Unlikely in subject/body; separates fields within one git-log record when using -z.
_GIT_MSG_FIELD_SEP = "\x1f"

# Read chunk size for streaming git log stdout (bound on incomplete buffer growth).
_GIT_LOG_STREAM_CHUNK = 256 * 1024

# Cap on bytes held in the parse buffer / a single yielded record (process RAM).
# ``0`` = unlimited. Override: GIT_CALCULATOR_COMMIT_MSG_MAX_RECORD_BYTES
_DEFAULT_MAX_RECORD_BYTES = 4 * 1024 * 1024  # 4 MiB — well above typical commit messages


def _env_nonneg_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def _max_record_bytes() -> int:
    return _env_nonneg_int(
        "GIT_CALCULATOR_COMMIT_MSG_MAX_RECORD_BYTES", _DEFAULT_MAX_RECORD_BYTES
    )


def _parse_commit_message_record(record: str) -> CommitMessageRecord | None:
    if not record.strip():
        return None
    parts = record.split(_GIT_MSG_FIELD_SEP, 3)
    if len(parts) < 2:
        return None
    sha = parts[0].strip()
    if len(sha) != 40:
        return None
    subj = parts[1]
    body = parts[2] if len(parts) > 2 else ""
    raw_b = parts[3] if len(parts) > 3 else ""
    return sha, subj, body, raw_b


def _check_record_size(nbytes: int, *, what: str) -> None:
    limit = _max_record_bytes()
    if limit and nbytes > limit:
        raise CommitMessagesBatchMemoryError(
            f"commit-message stream {what} exceeded "
            f"{nbytes} bytes (limit {limit}); "
            f"raise GIT_CALCULATOR_COMMIT_MSG_MAX_RECORD_BYTES or narrow scope"
        )


def iter_commit_message_records_from_stream(
    stream: TextIO, *, chunk_size: int = _GIT_LOG_STREAM_CHUNK
) -> Iterator[CommitMessageRecord]:
    """
    Yield ``(sha, subject, body, raw_B)`` from a NUL-delimited git-log text stream.

    Peak retained state is the incomplete read buffer plus the current record —
    not the full history. Callers decide whether to discard, persist, or index.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    buf = ""
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        buf += chunk
        _check_record_size(len(buf), what="incomplete buffer")
        while True:
            nul = buf.find("\0")
            if nul < 0:
                break
            raw_record, buf = buf[:nul], buf[nul + 1 :]
            _check_record_size(len(raw_record), what="record")
            parsed = _parse_commit_message_record(raw_record)
            if parsed is not None:
                yield parsed
    if buf.strip():
        _check_record_size(len(buf), what="record")
        parsed = _parse_commit_message_record(buf)
        if parsed is not None:
            yield parsed


def iter_git_log_commit_messages() -> Iterator[CommitMessageRecord]:
    """
    One ``git log --all --reflog -z`` process; yield each commit's message fields.

    More efficient than per-commit ``git log -n 1`` (one process, streamed stdout).
    Does not build an in-memory map — consumers iterate and retain only what they need.
    """
    fmt = f"%H{_GIT_MSG_FIELD_SEP}%s{_GIT_MSG_FIELD_SEP}%b{_GIT_MSG_FIELD_SEP}%B"
    cmd = ["git", "log", "--all", "--reflog", "-z", f"--pretty=format:{fmt}"]
    if os.environ.get("GIT_CALCULATOR_SILENCE_GIT_RUN") != "1":
        print("# $> git", *cmd[1:])

    proc = sp_popen(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=_GIT_LOG_STREAM_CHUNK,
    )
    assert proc.stdout is not None
    stderr = ""
    try:
        yield from iter_commit_message_records_from_stream(proc.stdout)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            stderr = proc.stderr.read()
            proc.stderr.close()
        code = proc.wait()
    if code != 0:
        raise RuntimeError(
            f"git log commit-message stream failed (exit {code}): {stderr.strip()}"
        )


def git_log_commit_messages_batch() -> CommitMessagesBatch:
    """
    Convenience: materialize ``iter_git_log_commit_messages()`` into a sha→messages map.

    Prefer ``iter_git_log_commit_messages()`` when you can process one record at a time;
    this helper still loads the full map into RAM (same shape as before for callers).
    """
    out: CommitMessagesBatch = {}
    for sha, subj, body, raw_b in iter_git_log_commit_messages():
        out[sha] = (subj, body, raw_b)
    return out
