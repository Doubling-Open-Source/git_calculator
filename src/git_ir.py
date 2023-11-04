from collections import defaultdict
from src.util.git_util import git_run

class git_sha(str):
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

class get_obj(git_sha):
    """
    A class used to represent a Git object, inheriting from base 'git_sha' class.

    Attributes:
    -----------
    __all_obj__ : dict
        A class-level dictionary that keeps track of all instantiated objects.

    Methods:
    --------
    __new__(cls, sha):
        Constructs a new instance and registers it in '__all_obj__'.
    _link():
        Establishes parent-child relationships between Git objects.
    link_children():
        Ensures all objects in '__all_obj__' have established their links.
    _from_cat_file(sha):
        Creates a Git object from the 'git cat-file' command output.
    _from_show(sha):
        Creates a Git object from the 'git show' command output.
    obj(sha):
        Retrieves a Git object by its SHA, or creates it if it doesn't exist.
    commit(commit_time, commit_hash, tree_hash, parent_hashs, author_email, author_name):
        Creates and initializes a detailed Git object representing a commit.
    __repr__():
        Returns a formatted string representing the Git object's essential details.
    """
    __all_obj__ = {}

    def __new__(cls, sha):
        """
        Overrides the default method for object creation, ensuring each 'git_obj' instance is unique
        by its 'sha' and stored in the '__all_obj__' dictionary.

        Parameters:
        -----------
        sha : str
            The unique SHA hash representing a Git object.

        Returns:
        --------
        git_obj
            The newly created 'git_obj' instance.
        """
        res = super().__new__(cls, sha)
        cls.__all_obj__[sha] = res
        return res
    
    def _link(self):
        """
        Identifies and links parent objects to their children, establishing a bidirectional
        relationship in the Git history graph.

        Ensures that the current object is registered as a child of each of its parents.
        """
        for p in self._parents:
            try:
                p = self.obj(p)
                if self not in p._children:
                    p._children.append(self)
            except KeyError:
                pass

    @classmethod
    def link_children(cls):
        """
        Iterates through all instantiated 'git_obj' objects and ensures they are properly linked
        to their parent objects. This method helps in building the complete Git history graph.
        """
        for o in cls.__all_obj__.values():
            o._link()

    @classmethod    
    def _from_cat_file(cls, sha):
        """
        Generates a 'git_obj' instance based on the content extracted from the 'git cat-file' command,
        parsing necessary information such as tree, parents, and author details.

        Parameters:
        -----------
        sha : str
            The unique SHA hash for a Git object.

        Returns:
        --------
        git_obj
            The newly created 'git_obj' instance with properties extracted from 'git cat-file'.
        """
        cmd = git_run('cat-file','-p', sha)
        res = get_obj(sha)

        tree = auth = None
        res._parents = []
        for line in cmd.stdout.splitlines():
            denom, _ ,line = line.strip().partition(' ')
            if denom == 'tree':
                tree = line
            elif denom == 'parent':
                res._parents.append(line)
            elif denom == 'committer':
                line, timestamp, _tz = line.rsplit(' ', 5)
                res._when = int(timestamp)  # TODO: Do something with tz
                if line.endswith('>'):
                    auth, _, email= line[:-1].partition('<')
                    auth = auth.strip()
                    res._author = (auth, email)
                else:
                    res._author = (line.strip(), None)
        return res

    @classmethod
    def _from_show(cls, sha):       
        """
        Constructs a 'git_obj' instance based on the output of the 'git show' command. It parses the
        command's output to extract detailed commit information.

        Parameters:
        -----------
        sha : str
            The unique SHA hash for a Git object.

        Returns:
        --------
        git_obj
            The 'git_obj' instance initialized with commit details.
        """ 
        cmd = git_run('show', r'--format=%ct|%H|%T|%P|%ae|%an', '-s', ''+sha)
        line = cmd.stdout.strip()
        parts = line.split('|', 5)
        parts[3] = parts[3].split()  # Multiple parents
        return get_obj.commit(*parts)

    @classmethod
    def obj(cls, sha):
        """
        Retrieves the 'git_obj' instance corresponding to the given SHA if it exists. Otherwise, it
        tries to generate the 'git_obj' from existing data or by using the 'git show' command.

        Parameters:
        -----------
        sha : str
            The unique SHA hash for a Git object.

        Returns:
        --------
        git_obj
            The corresponding 'gitobj' instance.
        """
        try:
            return cls.__all_obj__[sha]
        except KeyError:
            for k, v in cls.__all_obj__.items():
                if k.startswith(sha):
                    return v
            return cls._from_show(sha)
    
    @classmethod
    def commit(cls, commit_time, commit_hash, tree_hash, parent_hashs, author_email, author_name):
        """
        Instantiates and initializes a 'git_obj' instance that represents a detailed Git commit,
        including information about the commit's time, tree, parents, and author.

        Parameters:
        -----------
        commit_time : str
            The timestamp of the commit.
        commit_hash : str
            The unique SHA hash of the commit.
        tree_hash : str
            The SHA hash of the tree object this commit points to.
        parent_hashs : list
            A list of SHA hashes for the parents of the commit.
        author_email : str
            The email address of the author of the commit.
        author_name : str
            The name of the author of the commit.

        Returns:
        --------
        git_obj
            The newly initialized 'git_obj' instance representing a commit.
        """        
        res = cls(commit_hash)
        res._type = '<<' if len(parent_hashs) > 1 else '<'
        res._when = int(commit_time)
        res._author = (author_email, author_name)
        res._tree = git_sha(tree_hash)
        res._children = []
        res._parents = tuple(git_sha(p) for p in parent_hashs)
        return res
            
    def __repr__(self):
        """
        Generates a human-readable representation of the 'git_obj' instance, primarily for debugging
        and logging purposes. It includes the SHA, type of commit, parents, and author information.

        Returns:
        --------
        str
            A string representation of the 'git_obj' instance.
        """        
        auth = self._author[0] if '@' in self._author[0] else repr(self._author[1])
        par = ''
        if len(self._parents) > 1:
            par = ','.join(repr(p) for p in self._parents)
        elif len(self._parents) == 1:
            par = repr(self._parents[0]) 
        return f"{self!s} {self._type} {par} {auth}"
    

def all_objects():
    cmd = git_run('rev-list', '--all', '--objects')
    res = {git_sha(line.split()[0]): None for line in cmd.stdout.splitlines()}
    res = list(res.keys())  # Sorted uniq
    return res