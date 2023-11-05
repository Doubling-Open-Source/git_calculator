from collections import defaultdict
from src.util.git_util import git_run
from dataclasses import dataclass, field
from subprocess import run as sp_run
import time
from functools import partial
from statistics import mean, median, stdev, quantiles
from io import StringIO

quartiles = partial(quantiles, method='inclusive', n=4)

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

class git_obj(git_sha):
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
        return git_obj.commit(*parts)

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
    """
    Retrieve a list of unique Git objects (e.g., commits, blobs, trees) present in the entire Git repository.

    This function uses Git's 'rev-list' command with the '--all' and '--objects' options to list all objects
    reachable from any branch or reference in the repository. It then processes the output to extract and return
    a list of unique Git object hashes.

    Returns:
        list of str: A list containing the unique Git object hashes found in the repository.

    Example:
        >>> all_objects()
        ['d1a7f4b29c79a11f08f2cdac7fe13c3d9ec19025', '6a2e78cf73ea38c614f96e8950a245b52ad7fe7c']
    """
    cmd = git_run('rev-list', '--all', '--objects')
    res = {git_sha(line.split()[0]): None for line in cmd.stdout.splitlines()}
    res = list(res.keys())  # Sorted uniq
    return res

def git_log():
    """
    Retrieve and parse Git commit log entries from the entire Git repository.

    This function uses Git's 'log' command with various options to obtain commit log entries from all branches and
    reflogs in the repository. It parses each log entry and creates Git commit objects with attributes such as
    commit timestamp, SHA hash, tree hash, parent commits, author email, and author name.

    After parsing, it links parent-child relationships between commits and calibrates the minimum SHA hash length.

    Returns:
        list of GitCommit: A list containing parsed Git commit objects representing the commit history.

    Note:
        The function assumes the availability of the 'git_run', 'git_obj', and 'git_sha' modules for running Git
        commands, creating Git commit objects, and handling SHA hashes, respectively.

    Example:
        >>> git_log()
        [
            GitCommit(
                timestamp=1591272869,
                sha='d1a7f4b29c79a11f08f2cdac7fe13c3d9ec19025',
                tree_sha='6a2e78cf73ea38c614f96e8950a245b52ad7fe7c',
                parents=['8d9a6d22dded20b4f6642ac21c64efab8dd9e78b'],
                author_email='author@example.com',
                author_name='Author Name'
            ),
            ...
        ]
    """
    def to_obj(line):
        parts = line.split('|', 5)
        parts[3] = parts[3].split()  # Multiple parents
        return git_obj.commit(*parts)
    res = [
        to_obj(line)
        for line in git_run('log','--all','--reflog',r'--format=%ct|%H|%T|%P|%ae|%an').stdout.splitlines()
    ]
    git_obj.link_children()
    git_sha.calibrate_min()
    return res

def git_branches():
    """
    Retrieve and parse Git branch information from the repository.

    This function uses Git's 'branch' command with various options to obtain information about all branches,
    including local and remote branches, in the repository. It parses each branch entry and creates a dictionary
    where keys are branch names, and values are associated object names (e.g., commit hashes).

    Returns:
        dict: A dictionary containing branch names as keys and associated object names as values.

    Example:
        >>> git_branches()
        {
            'master': 'd1a7f4b29c79a11f08f2cdac7fe13c3d9ec19025',
            'feature/branch-a': '6a2e78cf73ea38c614f96e8950a245b52ad7fe7c',
            'origin/develop': '8d9a6d22dded20b4f6642ac21c64efab8dd9e78b',
            ...
        }
    """
    def to_obj(line):
        parts = line.split(' ', 2)
        return (parts[0], parts[2])
    res = [
        to_obj(line)
        for line in git_run('branch','-al','--no-abbrev',r'--format=%(objectname) %(objecttype) %(refname)').stdout.splitlines()
    ]
    return dict(res)


@dataclass
class BranchLine:
    visited: set[git_obj] = field(compare=False) # Shared set within a cloud of branchlines, init with empty set
    strategy: str = field(compare=False) # top, reverse, 
    start: git_obj = field(compare=False)
    merge: git_obj = None
    departure: git_obj = None
    commits: list[git_obj] = field(default_factory=list, compare=False)
    merges: list['BranchLine'] = field(default_factory=list, compare=False)

    def tree(self):
        queue = [self]
        while queue:
            for branch in queue:
                yield branch
                queue.extend(branch.merges)
            del queue[:]

    def __len__(self):
        return 2 + len(self.commits)

    def __iter__(self):
        if self.merge:
            yield self.merge
        for c in self.commits:
            yield c
        if self.departure:
            yield self.departure

    def add(self, o):
        o = git_obj.obj(o)
        if o not in self.visited:
            self.visited.add(o)
        # if len(o._children) <= 1:
            self.commits.append(o)
            return o
        return None

    def branch_line(self, o):
        o = self.add(o)
        while o and o._parents:
            p = git_obj.obj(o._parents[0])
            o = self.add(p)
            if not o:
                self.departure = p

    def __post_init__(self):
        self.start = git_obj.obj(self.start)
        self.branch_line(self.start)
        if self.strategy == 'top':
            # Branch goes on to last merge
            for c in self.commits:  
                for p in c._parents[1:]:
                    self.merges.append(BranchLine(self.visited, self.strategy, p, c))
        elif self.strategy == 'reverse':
            # Branch goes on until first merge
            for c in reversed(self.commits):  # Branch goes until first merge, if natural order then to last merge
                for p in c._parents[1:]:
                    self.merges.append(BranchLine(self.visited, self.strategy, p, c))
        elif self.strategy == 'narrow':
            # Follow each branch to the end before diving in
            self.narrow()
        elif self.strategy == 'stop':
            # Don't recurse
            pass
        else:
            raise ValueError("Unknown strategy: " + self.strategy)
        
    def narrow(self, subs=None):
        # Build all my sub branches (narrow)
        for c in self.commits:  
            for p in c._parents[1:]:
                self.merges.append(BranchLine(self.visited, 'stop', p, c))
        if subs is not None:
            subs.extend(self.merges)
            return
        subs = list(self.merges)
        i = 0
        while True:
            if i >= len(subs):
                break
            m = subs[i]
            i += 1
            if m.strategy == 'stop':
                m.strategy = 'narrow'
                m.narrow(subs)

    def _dot(self, res, limit, show_nodes):
        """
        Retval res, pass in a list for all the dot-strings.
        """
        def node(n):
            res = '' + n
            return f'"{res[:7]}"'

        print(f"# {gitsha(self.merge)} {len(res)}")
        res.append(f"/* {self.pretty()} */")
        displayed = []
        if not self.commits:
            if self.merge and self.departure:
                res.append(f"{node(self.departure)} -> {node(self.merge)} [style=dotted];")
                displayed += [node(self.merge), node(self.departure)]
        else:
            tmp = [node(c) for c in reversed(self.commits)]
            reserved = [node(r) for r in show_nodes.intersection(self.commits)]

            if self.departure:
                res.append(f"{node(self.departure)} [shape=box];")
                res.append(f"{node(self.departure)} -> {tmp[0]};")
                displayed.append(node(self.departure))

            if show_nodes:
                show = []
                skip = 0
                for t in tmp:
                    if t == tmp[0] or t == tmp[-1] or t in reserved:
                        if skip:
                            show.append(skip)
                        show.append(t)
                        displayed.append(t)
                        skip = 0
                    else:
                        skip += 1
                line = []
                print("# SHOW:", show)
                for i, n in enumerate(show):
                    print(f"# {i} LINE ({n}):", line)
                    if isinstance(show[i], int):
                        skip = show[i]
                        if len(line) > 1:
                            res.append(' -> '.join(line) + ';')
                            line = [line[-1]]
                        continue

                    if i and isinstance(show[i-1], int):
                        assert(len(line) == 1)
                        line.append(n)
                        if skip == 1:
                            res.append(' -> '.join(line) + " [label=\"One hidden\"];")
                        else:
                            res.append(' -> '.join(line) + f" [label=\"{skip} hidden commits\"];")
                        line = [line[-1]]
                        continue

                    line.append(n)

                if len(line) > 1:
                    res.append(' -> '.join(line) + ';')

            else:
                head = tmp[:limit//2]
                tail = tmp[-limit//2:]
                if len(tmp) == 1:
                    if not self.merge and not self.departure:
                        res.append(tmp[0] + '; /* alone */')
                elif len(self.commits) <= limit or (len(head) + len(tail) + 1 == len(tmp)):
                    res.append(' -> '.join(tmp) + ";")
                else:
                    if len(head) > 1:
                        res.append(' -> '.join(head) + ";")
                    res.append(f"{head[-1]} -> {tail[0]} [label=\"{len(tmp)-len(head)-len(tail)} hidden commits\"];")
                    if len(tail) > 1:
                        res.append(' -> '.join(tail) + ";")

            if self.merge:
                res.append(f"{node(self.merge)} [shape=box];")
                res.append(f"{tmp[-1]} -> {node(self.merge)};")
                displayed.append(node(self.merge))

        for m in self.merges:
            displayed += m._dot(res, limit, show_nodes)
        return displayed

    def dot(self, limit=3, fname=None):
        def _show_nodes(n, merges, departures):
            if n.commits:
                if n.merge:
                    merges.append(n.merge)
                if n.departure:
                    departures.append(n.departure)
            for s in n.merges:
                _show_nodes(s, merges, departures)

        def human_t(t):
            t /= 3600
            if t > 24:
                t /= 24
                return f"{t:,.1f}d"
            t = int(t)
            if not t:
                return '-'
            m = t % 60
            return f"{t:,d}h {m:02,d}m"
            

        _merges, _departures = [], []
        _show_nodes(self, _merges, _departures)
        _show = set(_merges + _departures)
        res = ["digraph Branches {"]
        displayed = self._dot(res, limit, _show)
        print("# Displayed:", len(displayed), list(displayed)[:3], '...')

        # COLOR LONG BRANCHES
        trees = sorted([(len(t), t) for t in self.tree()], reverse=True, key=lambda x:x[0])
        colors = ['aquamarine', 'cadetblue1', 'darkseagreen1', 'thistle', 'mistyrose', 'peachpuff']
        print("# Longest trees:", [(l, ) for l, t in trees])
        gb = git_branches()
        for (_, t), color in zip(trees, colors):
            print("# start", t.start)
            print("# departure", t.departure)
            # res.append(f'{t.start} [style=filled,fillcolor={color}];')
            last = None
            for c in t:
                last = c
                cc = '' + c
                c = f'"{cc[:7]}"'
                if c in displayed:
                    if cc in gb:
                        print("# LABELED BRANCH", cc, gb[cc])
                        _, _, name = gb[cc].rpartition('/origin/')
                        res.append(f'{c} [style=filled,fillcolor={color},label="{cc[:7]}\\n{name}"];')
                    else:
                        res.append(f'{c} [style=filled,fillcolor={color}];')
        
        # ADD CYCLETIME TO DOT
        for _, t in trees:
            last = None
            for c in t:
                c = ('' + c)[:7]
                if f'"{c}"' in displayed:
                    last = c
            if last and t.commits:
                _, ramp, work, close, total = t._cycle()
                total -= (ramp or 0) / 2
                work = (work or 0) + (ramp or 0) / 2
                if work and close and human_t(work) != '-':
                    res.append(f'"{c}_ct" [shape=circle,arrowhead=none,fillcolor=yellow,style=filled,'
                               f'label=\"{human_t(total)} total =\\n{human_t(work)} work\\n{human_t(close)} merge\"];')
                    res.append(f'"{c}_ct" -> "{c}";')

        res.append("}")
        # dedupe = {r:None for r in res}
        if fname:
            fname, ext = os.path.splitext(fname)
            with open(fname + '.dot', 'wt') as fout:
                print(*res, file=fout, sep='\n')
            if ext != '.dot':
                ext = ext[1:]
                sp_run(['dot', f'-T{ext}', f'-o{fname}.{ext}', f'{fname}.dot'], check=True)
                print(f"# CREATED {fname}.{ext} from {fname}.dot")
                sp_run(['open', f'{fname}.{ext}'])
        return res
        
    def get_commits(self):
        if self.strategy in ('narrow', 'top'):
            return self.commits
        if self.strategy == 'reverse':
            res = []
            for c in reversed(self.commits):
                res.append(c)
                if len(c._children ) > 1:
                    # first merge
                    break
            return reversed(res)
        

    def pretty(self, limit=3):
        if len(self.commits) <= limit:
            return f"{git_sha(self.merge)} <- {[git_sha(c) for c in self.commits]} <- {git_sha(self.departure)}"

        return (f"{git_sha(self.merge)} <- [{git_sha(self.start)} ..({len(self.commits)-2}).. "
                f"{git_sha(self.commits[-1])}] <- {git_sha(self.departure)}")
    
    def _cycle(self):
        start = total = ramp = close = work = None
        ts = [c._when for c in self]
        if ts:
            start = min(ts)
            if len(ts) > 1:
                total = max(ts) - min(ts)
            if self.departure and self.commits:
                ramp = min(ts[1:-1]) - self.departure._when
            if self.merge and self.commits:
                close = self.merge._when - max(ts[1:-1])
            if self.commits:
                work = max(ts[1:-1]) - min(ts[1:-1])
        # print(start, ramp, work, close, total)
        return start, ramp, work, close, total
    
    def cycletime(self, fname=None, bucket_size=None):
        def ts(d,b=None):
            if d is None:
                return '-'
            a=None
            if b:
                a = b
                d = b-a
            h=d // 3600
            days = h // 24
            h = h % 24
            if not days:
                m = ((d//60) % 60) / 60.0
                return f"{h+m:.1f}h"
            return f"{int(d):,d}d {h}h"
        
        def flip_cycle(cycles):
            ss, rr, ww, cc, tt = [], [], [], [], []
            for s, r, w, c, t in cycles:
                ss.append(s)
                rr.append(r)
                ww.append(w)
                cc.append(c)
                tt.append(t)
            return ss, rr, ww, cc, tt

        _gb = git_branches()
        _trees = sorted([(len(t), t) for t in self.tree()], reverse=True, key=lambda x:x[0])
       
        span = [(t._cycle(), t) for t in self.tree()]
        span = [t for t in span if t[1].commits and t[0][1]] # Make sure we have ramp
        pprint([s for s, _ in span])
        span = sorted(span)
        step = bucket_size or max(1, len(span)//12)
        print("# STEP", step)
        print("CYCLE TIME ANALYSIS [days]")
        buf = StringIO()
        print("INTERVAL START, BRANCHES, COMMITS,",
              "p50 COMMITS, p50 CYCLETIME, p50 QA, p50 WORKTIME,",
              "p75 COMMITS, p75 CYCLETIME, p75 QA, p75 WORKTIME,",
              "avg COMMITS, avg CYCLETIME, avg QA, avg WORKTIME,",
              "std COMMITS, std CYCLETIME, std QA, std WORKTIME,", file=buf)
        for i in range(0, len(span), step):
            sub = span[i:i+step]
            ss, rr, ww, cc, tt = flip_cycle(c for c, _ in sub)
            rr = [round(i/3600/24,2) for i in rr]
            ww = [round(i/3600/24,2) for i in ww]
            cc = [round(i/3600/24,2) for i in cc]
            tt = [round(i/3600/24,2) for i in tt]
            wt = [(r or 0)//2 + (w or 0) for r,w in zip(rr, ww)] # Half ramp + work time
            ct = [(t or 0) - (r or 0)//2 for r,t in zip(rr, tt)] # Total - half ramp 
            com = [len(t.commits) for _, t in sub]
            print(time.ctime(ss[0]), len(sub), sum(com), 
                  *[round(v,2) for v in [median(com), median(ct), median(cc), median(wt),
                                         quartiles(com)[2], quartiles(ct)[2], quartiles(cc)[2], quartiles(wt)[2],
                                         mean(com), mean(ct), mean(cc), mean(wt),
                                         stdev(com), stdev(ct), stdev(cc), stdev(wt)]],
                  sep=',', file=buf)
        if fname is None:
            print(buf.getvalue())
        else:
            with open(fname, 'wt') as fout:
                print(buf.getvalue(), file=fout)
            if fname.endswith('.csv'):
                sp_run(['open', fname])
        return buf.getvalue()

def branch_lines(o):
    res = BranchLine(set(), o)
    git_sha.calibrate_min()
    return res  