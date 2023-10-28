from subprocess import run as sp_run
from collections import defaultdict

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


class gitsha(str):
    """
    A custom string class for representing Git SHA hashes.

    This class allows for the creation of Git SHA hash objects with a specified
    display length. It also provides a method to calibrate the display length
    of Git SHA hash objects based on common prefixes among instances.

    Attributes:
        __all_gitsha__ (set): A set to store all instances of the gitsha class.

    Args:
        sha (str): The Git SHA hash string.

    Attributes:
        _show_ (int): The display length of the Git SHA hash.

    Methods:
        __new__(cls, sha): Create a new gitsha instance.
        __str__(self): Return a string representation of the gitsha with a length of _show_.
        __repr__(self): Return a string representation of the gitsha with a length of _show_.
        calibrate_min(cls): Calibrate the display length of gitsha objects with common prefixes.
    """
    # Set to store all instances of the gitsha class
    __all_gitsha__ = set()

    def __new__(cls, sha):
        sha = sha or ''  # Strip the None
        res = super().__new__(cls, sha)
        res._show_ = 4
        cls.__all_gitsha__.add(res)
        return res

    def __str__(self):
        return self[:self._show_]
    
    def __repr__(self):
        return self[:self._show_]
    
class gitsha(str):
    __all_gitsha__ = set()

    def __new__(cls, sha):
        sha = sha or ''  # Strip the None
        res = super().__new__(cls, sha)
        res._show_ = 4
        cls.__all_gitsha__.add(res)
        return res

    def __str__(self):
        return self[:self._show_]
    
    def __repr__(self):
        return self[:self._show_]
    
    @classmethod
    def get_instance(cls, sha_value):
        """Retrieve a gitsha instance by its SHA value."""
        # Iterate through the set of stored instances and find the one with the matching value.
        for instance in cls.__all_gitsha__:
            if instance == sha_value:
                return instance
        return None  # Return None if no instance matches the value.

    @classmethod
    def calibrate_min(cls):
        # Flag to track whether we need another pass to check for duplicates
        need_another_pass = True

        while need_another_pass:
            # Reset the flag for each pass
            need_another_pass = False

            # Dictionary to store the initial part of the sha and the corresponding full objects
            sha_dict = defaultdict(list)

            # Populate the dictionary with the current _show_ state
            for sha in cls.__all_gitsha__:
                current_prefix = sha[:sha._show_]
                sha_dict[current_prefix].append(sha)

            # Check for duplicates and adjust _show_ accordingly
            for prefix_group in sha_dict.values():
                if len(prefix_group) > 1:
                    # If we found duplicates, we plan for another checking pass
                    need_another_pass = True

                    # Since these are duplicates, increase their _show_ attribute
                    for item in prefix_group:
                        item._show_ += 1  # This will affect their representation in the next pass

        # The loop continues until there are no duplicates, ensuring all shas are unique with their _show_ state.


