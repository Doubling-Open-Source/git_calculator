"""BranchLine helpers in ``cycle_time_by_branches`` (not schema_metrics)."""

from __future__ import annotations

from src.calculators.cycle_time_by_branches import BranchLine

class _T:
    __slots__ = ("_when",)

    def __init__(self, w: int) -> None:
        self._when = w


def test_cycle_merge_plus_one_commit_no_departure_no_valueerror():
    bl = BranchLine.__new__(BranchLine)
    bl.merge = _T(30)
    bl.commits = [_T(20)]
    bl.departure = None

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start == 20
    assert total == 10
    assert ramp is None
    assert work == 0
    assert close == 10


def test_cycle_happy_path_all_nodes_present():
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = [_T(20), _T(30)]
    bl.merge = _T(40)

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start == 10
    assert total == 30  # 40 - 10
    assert ramp == 10   # 20 - 10
    assert work == 10   # 30 - 20
    assert close == 10  # 40 - 30


def test_cycle_single_commit():
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = [_T(20)]
    bl.merge = _T(30)

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start == 10
    assert total == 20
    assert ramp == 10   # 20 - 10
    assert work == 0
    assert close == 10  # 30 - 20


def test_cycle_no_commits():
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = []
    bl.merge = _T(20)

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start == 10
    assert total == 10
    assert ramp is None
    assert work is None
    assert close is None


def test_cycle_ongoing_branch_no_merge():
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = [_T(20), _T(30)]
    bl.merge = None

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start == 10
    assert total == 20  # 30 - 10
    assert ramp == 10   # 20 - 10
    assert work == 10   # 30 - 20
    assert close is None


def test_cycle_completely_empty():
    bl = BranchLine.__new__(BranchLine)
    bl.departure = None
    bl.commits = []
    bl.merge = None

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert start is None
    assert ramp is None
    assert work is None
    assert close is None
    assert total is None

def test_cycle_work_bounds_independent_of_total_bounds():
    # Proves that `first_c` and `last_c` only evaluate commits, not all_ts.
    # If they evaluated all_ts, work would be 90 (100 - 10) instead of 10.
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = [_T(50), _T(60)] # Work is strictly 10
    bl.merge = _T(100)

    start, ramp, work, close, total = BranchLine._cycle(bl)
    assert total == 90
    assert work == 10
    assert ramp == 40
    assert close == 40


def test_cycle_ignores_leaked_boundary_nodes_in_commits():
    # If departure or merge accidentally end up in the commits list,
    # the function should filter them out so they don't corrupt the work phase.
    bl = BranchLine.__new__(BranchLine)
    dep = _T(10)
    merge = _T(40)

    bl.departure = dep
    bl.merge = merge
    # Now we are actually simulating the leak!
    bl.commits = [dep, _T(20), _T(30), merge]

    start, ramp, work, close, total = BranchLine._cycle(bl)

    # With proper filtering, work remains strictly 10 (30 - 20)
    assert work == 10
    assert ramp == 10
    assert close == 10

def test_cycle_commits_out_of_order():
    # Commits appear out of chronological order (common in git histories)
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(10)
    bl.commits = [_T(40), _T(20), _T(50), _T(30)]
    bl.merge = _T(60)

    start, ramp, work, close, total = BranchLine._cycle(bl)

    # min(commits) is 20, max(commits) is 50
    assert total == 50  # 60 - 10
    assert ramp == 10   # 20 - 10
    assert work == 30   # 50 - 20
    assert close == 10  # 60 - 50

def test_cycle_orphan_commits_only():
    # An active branch where the fork point (departure) wasn't found
    bl = BranchLine.__new__(BranchLine)
    bl.departure = None
    bl.commits = [_T(20), _T(30), _T(40)]
    bl.merge = None

    start, ramp, work, close, total = BranchLine._cycle(bl)

    assert start == 20
    assert total == 20  # 40 - 20
    assert ramp is None
    assert work == 20   # 40 - 20
    assert close is None

def test_cycle_instantaneous_lifecycle():
    # Departure, commit, and merge all share the exact same timestamp
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(100)
    bl.commits = [_T(100)]
    bl.merge = _T(100)

    start, ramp, work, close, total = BranchLine._cycle(bl)

    assert start == 100
    assert total == 0
    assert ramp == 0
    assert work == 0
    assert close == 0

def test_cycle_clock_skew_negative_phases():
    # A commit timestamp predates the departure (e.g. cherry-pick or clock skew)
    # and another commit postdates the merge timestamp.
    bl = BranchLine.__new__(BranchLine)
    bl.departure = _T(50)
    bl.commits = [_T(10), _T(90)] # First commit is "before" departure!
    bl.merge = _T(80)             # Merge is "before" last commit!

    start, ramp, work, close, total = BranchLine._cycle(bl)

    # Start should be the absolute lowest timestamp across all nodes
    assert start == 10

    # Total should be absolute highest (90) - absolute lowest (10)
    assert total == 80

    # Ramp: first_c (10) - dep (50) = -40
    assert ramp == -40

    # Work: last_c (90) - first_c (10) = 80
    assert work == 80

    # Close: merge (80) - last_c (90) = -10
    assert close == -10