from subprocess import run as sp_run

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

