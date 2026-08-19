"""
Python-materialized storage check for ``metrics_cycle_time_by_branches`` (ADR 0010).

Legacy ``BranchLine`` is the source of truth. Rows are written from Python using
``commits_export`` + ``commit_parent_edges``, then read back — this checks table
round-trip / serialization, **not** an independent SQL graph materialization.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import sqlite3

from git_calculator.calculators.cycle_time_by_branches import BranchLine
from git_calculator.calculators.sqlite_lake.schema import get_full_sha
from git_calculator.git_ir import git_obj

from ._common import bind_materialization_params, read_schema_sql

_DUMMY_TREE = "0" * 40


@dataclass(frozen=True)
class CanonicalBranchLine:
    branch_line_id: str
    strategy: str
    root_sha: str
    merge_sha: Optional[str]
    departure_sha: Optional[str]
    commit_count: int
    ramp_seconds: Optional[int]
    work_seconds: Optional[int]
    close_seconds: Optional[int]
    total_seconds: Optional[int]


def stable_branch_line_id(strategy: str, merge_sha: Optional[str], root_sha: str) -> str:
    """Stable id: SHA-256 hex of (strategy, merge_sha or '', root_sha)."""
    ms = merge_sha or ""
    return hashlib.sha256(f"{strategy}\n{ms}\n{root_sha}".encode()).hexdigest()


def _ensure_metrics_table(conn: sqlite3.Connection) -> None:
    conn.executescript(read_schema_sql("metrics_cycle_time_by_branches.sql"))


def _parent_map(conn: sqlite3.Connection, repo_slug: str) -> Dict[str, List[str]]:
    cur = conn.execute(
        """
        SELECT child_sha, parent_sha, parent_ord
        FROM commit_parent_edges
        WHERE repo_slug = ?
        ORDER BY child_sha, parent_ord
        """,
        (repo_slug,),
    )
    out: Dict[str, List[str]] = {}
    for ch, pa, _ord in cur:
        out.setdefault(ch, []).append(pa)
    return out


def load_git_objects_from_commits_export(conn: sqlite3.Connection, repo_slug: str) -> None:
    """Rebuild ``git_obj`` graph from export tables (clears global ``git_obj`` cache first)."""
    git_obj.__all_obj__.clear()
    pmap = _parent_map(conn, repo_slug)
    rows = conn.execute(
        """
        SELECT sha, committed_at, author_ref
        FROM commits_export
        WHERE repo_slug = ?
        """,
        (repo_slug,),
    ).fetchall()
    for sha, committed_at, author_ref in rows:
        plist = pmap.get(sha, [])
        git_obj.commit(
            str(int(committed_at)),
            sha,
            _DUMMY_TREE,
            plist,
            author_ref,
            author_ref,
        )
    git_obj.link_children()


def _cycle_seconds(bl: BranchLine) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    _, ramp, work, close, total = bl._cycle()
    def _i(x: Any) -> Optional[int]:
        if x is None:
            return None
        return int(x)

    return _i(ramp), _i(work), _i(close), _i(total)


def canonical_from_branch_line(bl: BranchLine) -> CanonicalBranchLine:
    root_sha = get_full_sha(bl.start)
    merge_sha = get_full_sha(bl.merge) if bl.merge else None
    departure_sha = get_full_sha(bl.departure) if bl.departure else None
    bid = stable_branch_line_id(bl.strategy, merge_sha, root_sha)
    ramp_s, work_s, close_s, total_s = _cycle_seconds(bl)
    return CanonicalBranchLine(
        branch_line_id=bid,
        strategy=bl.strategy,
        root_sha=root_sha,
        merge_sha=merge_sha,
        departure_sha=departure_sha,
        commit_count=len(bl.commits),
        ramp_seconds=ramp_s,
        work_seconds=work_s,
        close_seconds=close_s,
        total_seconds=total_s,
    )


def legacy_branch_lines_canonical(
    root_sha: str,
    strategy: str,
) -> List[CanonicalBranchLine]:
    start = git_obj.obj(root_sha)
    root = BranchLine(set(), strategy, start)
    out = [canonical_from_branch_line(bl) for bl in root.tree()]
    return sorted(out, key=lambda r: r.branch_line_id)


def extract_cycle_time_by_branches_select() -> str:
    """Readback query over materialized rows (used for validation)."""
    return (
        "SELECT branch_line_id, strategy, root_sha, merge_sha, departure_sha, commit_count, "
        "ramp_seconds, work_seconds, close_seconds, total_seconds\n"
        "FROM metrics_cycle_time_by_branches\n"
        "WHERE repo_slug = :repo_slug AND dataset_id = :dataset_id\n"
        "ORDER BY branch_line_id"
    )


def run_cycle_time_by_branches_schema_select(
    conn: sqlite3.Connection, repo_slug: str, **kwargs: Any
) -> List[Tuple[Any, ...]]:
    cur = conn.execute(
        extract_cycle_time_by_branches_select(),
        bind_materialization_params(repo_slug, **kwargs),
    )
    return list(cur.fetchall())


def canonical_branch_lines_from_schema_rows(
    rows: Sequence[Tuple[Any, ...]],
) -> List[CanonicalBranchLine]:
    out: List[CanonicalBranchLine] = []
    for r in rows:
        out.append(
            CanonicalBranchLine(
                branch_line_id=str(r[0]),
                strategy=str(r[1]),
                root_sha=str(r[2]),
                merge_sha=str(r[3]) if r[3] is not None else None,
                departure_sha=str(r[4]) if r[4] is not None else None,
                commit_count=int(r[5]),
                ramp_seconds=int(r[6]) if r[6] is not None else None,
                work_seconds=int(r[7]) if r[7] is not None else None,
                close_seconds=int(r[8]) if r[8] is not None else None,
                total_seconds=int(r[9]) if r[9] is not None else None,
            )
        )
    return sorted(out, key=lambda x: x.branch_line_id)


def compare_branch_lines(
    py: Sequence[CanonicalBranchLine],
    sql: Sequence[CanonicalBranchLine],
) -> Optional[str]:
    a = sorted(py, key=lambda x: x.branch_line_id)
    b = sorted(sql, key=lambda x: x.branch_line_id)
    if len(a) != len(b):
        return f"cycle_time_by_branches row count py={len(a)} sql={len(b)}"
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"cycle_time_by_branches mismatch at {i}: py={x!r} sql={y!r}"
    return None


def _write_metrics_cycle_time_by_branches_rows(
    conn: sqlite3.Connection,
    repo_slug: str,
    rows: Sequence[CanonicalBranchLine],
    **kwargs: Any,
) -> None:
    params = bind_materialization_params(repo_slug, **kwargs)
    dataset_id = str(params["dataset_id"])
    computed_at = int(params["computed_at"])
    src_ver = params.get("source_commits_schema_version")
    tenant_id = params.get("tenant_id")

    conn.execute(
        "DELETE FROM metrics_cycle_time_by_branches WHERE repo_slug = ? AND dataset_id = ?",
        (repo_slug, dataset_id),
    )
    for r in rows:
        conn.execute(
            """
            INSERT INTO metrics_cycle_time_by_branches (
                repo_slug, dataset_id, branch_line_id, strategy, root_sha, merge_sha, departure_sha,
                commit_count, ramp_seconds, work_seconds, close_seconds, total_seconds,
                source_commits_schema_version, computed_at, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_slug,
                dataset_id,
                r.branch_line_id,
                r.strategy,
                r.root_sha,
                r.merge_sha,
                r.departure_sha,
                r.commit_count,
                r.ramp_seconds,
                r.work_seconds,
                r.close_seconds,
                r.total_seconds,
                src_ver,
                computed_at,
                tenant_id,
            ),
        )
    conn.commit()


def materialize_metrics_cycle_time_by_branches(
    conn: sqlite3.Connection,
    repo_slug: str,
    root_sha: str,
    strategy: str,
    **kwargs: Any,
) -> None:
    _ensure_metrics_table(conn)
    load_git_objects_from_commits_export(conn, repo_slug)
    rows = legacy_branch_lines_canonical(root_sha, strategy)
    _write_metrics_cycle_time_by_branches_rows(conn, repo_slug, rows, **kwargs)


def _edge_count(conn: sqlite3.Connection, repo_slug: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM commit_parent_edges WHERE repo_slug = ?",
        (repo_slug,),
    ).fetchone()
    return int(row[0]) if row else 0


def validate_cycle_time_by_branches_for_logs(
    logs: List[Any],
    repo_slug: str,
    conn: sqlite3.Connection,
    *,
    strategy: str = "top",
    on_ok_audit: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    if _edge_count(conn, repo_slug) == 0:
        return (
            "cycle_time_by_branches requires commit_parent_edges for the repo; "
            "missing edges (not a silent skip / not independent SQL parity)"
        )

    _ensure_metrics_table(conn)
    load_git_objects_from_commits_export(conn, repo_slug)
    root_sha = get_full_sha(logs[0])
    py = legacy_branch_lines_canonical(root_sha, strategy)
    _write_metrics_cycle_time_by_branches_rows(conn, repo_slug, py)
    sql_rows = run_cycle_time_by_branches_schema_select(conn, repo_slug)
    sql = canonical_branch_lines_from_schema_rows(sql_rows)
    err = compare_branch_lines(py, sql)
    if err is not None:
        return err
    if on_ok_audit is not None:
        on_ok_audit(
            f"python_materialized_roundtrip branch_lines={len(py)} strategy={strategy!r}"
        )
    return None
