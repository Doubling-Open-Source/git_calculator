import os
from subprocess import run as sp_run


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
    print('# $> git', *args)
    res = sp_run(['git']+list(args), check=True, text=True, capture_output=True)
    return res


