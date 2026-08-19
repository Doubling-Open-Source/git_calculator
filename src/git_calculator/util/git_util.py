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
from subprocess import run as sp_run

# sha -> (subject %s, body %b, full_message %B) from one git log -z pass.
CommitMessagesBatch = dict[str, tuple[str, str, str]]


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


def git_log_commit_messages_batch(work_style: str = "all-branches") -> CommitMessagesBatch:
    """
    One git invocation covering the same revisions as git_ir.git_log(work_style=...).

    Returns:
        Map full 40-char sha -> (subject %s, body %b, full_message %B) for populate + %B parity.
    """
    from git_calculator.work_style import log_revision_args

    fmt = f"%H{_GIT_MSG_FIELD_SEP}%s{_GIT_MSG_FIELD_SEP}%b{_GIT_MSG_FIELD_SEP}%B"
    res = git_run(
        "log",
        *log_revision_args(work_style),
        "-z",
        f"--pretty=format:{fmt}",
    )
    out: CommitMessagesBatch = {}
    if not res.stdout:
        return out
    for record in res.stdout.split("\0"):
        if not record.strip():
            continue
        parts = record.split(_GIT_MSG_FIELD_SEP, 3)
        if len(parts) < 2:
            continue
        sha = parts[0].strip()
        subj = parts[1]
        body = parts[2] if len(parts) > 2 else ""
        raw_b = parts[3] if len(parts) > 3 else ""
        if len(sha) == 40:
            out[sha] = (subj, body, raw_b)
    return out
