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
from subprocess import PIPE
from subprocess import Popen as sp_popen
from subprocess import run as sp_run

# sha -> (subject %s, body %b, full_message %B) from one git log -z pass.
CommitMessagesBatch = dict[str, tuple[str, str, str]]


class CommitMessagesBatchMemoryError(RuntimeError):
    """Raised when streaming commit-message batch exceeds configured memory caps."""


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

# Streaming read size for git log -z stdout (not the stored-message budget).
_GIT_LOG_STREAM_CHUNK = 1024 * 1024

# Defaults bound peak RAM for the returned map. ``0`` = unlimited for that knob.
# Override via env (bytes / counts are integers):
#   GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES
#   GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES
#   GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES
_DEFAULT_MAX_ENTRIES = 500_000
_DEFAULT_MAX_BYTES = 512 * 1024 * 1024
_DEFAULT_MAX_RECORD_BYTES = 16 * 1024 * 1024


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


def _stored_payload_bytes(sha: str, subj: str, body: str, raw_b: str) -> int:
    # Approximate retained size (Unicode code units ~ PyUnicode compact ASCII).
    return len(sha) + len(subj) + len(body) + len(raw_b)


def _parse_commit_message_record(record: str) -> tuple[str, str, str, str] | None:
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


def _enforce_batch_memory_caps(
    *,
    entries: int,
    total_bytes: int,
    record_bytes: int,
    max_entries: int,
    max_bytes: int,
    max_record_bytes: int,
) -> None:
    if max_record_bytes and record_bytes > max_record_bytes:
        raise CommitMessagesBatchMemoryError(
            f"commit message batch exceeded max record bytes "
            f"({record_bytes} > {max_record_bytes}); "
            f"raise GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES or narrow git log scope"
        )
    if max_entries and entries > max_entries:
        raise CommitMessagesBatchMemoryError(
            f"commit message batch exceeded max entries "
            f"({entries} > {max_entries}); "
            f"raise GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES or narrow git log scope"
        )
    if max_bytes and total_bytes > max_bytes:
        raise CommitMessagesBatchMemoryError(
            f"commit message batch exceeded max bytes "
            f"({total_bytes} > {max_bytes}); "
            f"raise GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES or narrow git log scope"
        )


def git_log_commit_messages_batch() -> CommitMessagesBatch:
    """
    One git invocation: all commits (--all --reflog), same coverage as git_ir.git_log().

    Streams ``git log -z`` stdout (no full-buffer ``capture_output``) and enforces
    optional memory caps so large repos fail fast instead of OOM.

    Returns:
        Map full 40-char sha -> (subject %s, body %b, full_message %B) for populate + %B parity.
    """
    max_entries = _env_nonneg_int(
        "GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_ENTRIES", _DEFAULT_MAX_ENTRIES
    )
    max_bytes = _env_nonneg_int(
        "GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_BYTES", _DEFAULT_MAX_BYTES
    )
    max_record_bytes = _env_nonneg_int(
        "GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES", _DEFAULT_MAX_RECORD_BYTES
    )

    fmt = f"%H{_GIT_MSG_FIELD_SEP}%s{_GIT_MSG_FIELD_SEP}%b{_GIT_MSG_FIELD_SEP}%B"
    cmd = ["git", "log", "--all", "--reflog", "-z", f"--pretty=format:{fmt}"]
    if os.environ.get("GIT_CALCULATOR_SILENCE_GIT_RUN") != "1":
        print("# $> git", *cmd[1:])

    out: CommitMessagesBatch = {}
    total_bytes = 0
    buf = ""

    proc = sp_popen(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1 << 20,
    )
    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(_GIT_LOG_STREAM_CHUNK)
            if not chunk:
                break
            buf += chunk
            if max_record_bytes and len(buf) > max_record_bytes and "\0" not in buf:
                raise CommitMessagesBatchMemoryError(
                    f"commit message batch exceeded max record bytes while reading "
                    f"(buffer {len(buf)} > {max_record_bytes} with no NUL); "
                    f"raise GIT_CALCULATOR_COMMIT_MSG_BATCH_MAX_RECORD_BYTES or narrow git log scope"
                )
            while True:
                nul = buf.find("\0")
                if nul < 0:
                    break
                record, buf = buf[:nul], buf[nul + 1 :]
                parsed = _parse_commit_message_record(record)
                if parsed is None:
                    continue
                sha, subj, body, raw_b = parsed
                record_bytes = _stored_payload_bytes(sha, subj, body, raw_b)
                next_entries = len(out) + (0 if sha in out else 1)
                next_total = total_bytes + record_bytes
                # Replacing an existing sha should not double-count entries.
                if sha in out:
                    prev = out[sha]
                    next_total = (
                        total_bytes
                        - _stored_payload_bytes(sha, prev[0], prev[1], prev[2])
                        + record_bytes
                    )
                _enforce_batch_memory_caps(
                    entries=next_entries,
                    total_bytes=next_total,
                    record_bytes=record_bytes,
                    max_entries=max_entries,
                    max_bytes=max_bytes,
                    max_record_bytes=max_record_bytes,
                )
                out[sha] = (subj, body, raw_b)
                total_bytes = next_total

        if buf.strip():
            parsed = _parse_commit_message_record(buf)
            if parsed is not None:
                sha, subj, body, raw_b = parsed
                record_bytes = _stored_payload_bytes(sha, subj, body, raw_b)
                next_entries = len(out) + (0 if sha in out else 1)
                next_total = total_bytes + record_bytes
                if sha in out:
                    prev = out[sha]
                    next_total = (
                        total_bytes
                        - _stored_payload_bytes(sha, prev[0], prev[1], prev[2])
                        + record_bytes
                    )
                _enforce_batch_memory_caps(
                    entries=next_entries,
                    total_bytes=next_total,
                    record_bytes=record_bytes,
                    max_entries=max_entries,
                    max_bytes=max_bytes,
                    max_record_bytes=max_record_bytes,
                )
                out[sha] = (subj, body, raw_b)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        stderr = ""
        if proc.stderr is not None:
            stderr = proc.stderr.read()
            proc.stderr.close()
        code = proc.wait()

    if code != 0:
        raise RuntimeError(
            f"git log commit-message batch failed (exit {code}): {stderr.strip()}"
        )
    return out
