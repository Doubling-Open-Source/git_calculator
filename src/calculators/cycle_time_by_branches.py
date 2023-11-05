from datetime import datetime
from io import StringIO
import time
from subprocess import run as sp_run
import numpy as np
from src.git_ir import all_objects, git_log, git_obj, git_sha, git_branches
from subprocess import run as sp_run
from dataclasses import dataclass, field
from subprocess import run as sp_run
from functools import partial
from statistics import mean, median, stdev, quantiles
import os
from pprint import pprint

quartiles = partial(quantiles, method='inclusive', n=4)

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

        print(f"# {git_sha(self.merge)} {len(res)}")
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