#!/usr/bin/env python3
"""
Compare cycle-time results: Python vs SQL.
Writes CSVs and plot images to an output directory. Use diff and snapshots to verify parity.

Ways to pick the repo to compare:

  1. Toy repo (deterministic):
     python scripts/compare_cycle_time_python_vs_sql.py --toy

  2. Another repo by path (run from git_calculator root):
     python scripts/compare_cycle_time_python_vs_sql.py --repo-dir /path/to/other/repo --out-dir scripts/compare_other_repo

  3. Current directory (cd into the repo first):
     cd /path/to/any/repo
     python /path/to/git_calculator/scripts/compare_cycle_time_python_vs_sql.py --out-dir ./compare_output

Output (all under --out-dir):
  CSVs: deltas_python.csv, deltas_sql.csv, fixed_bucket_*.csv, by_month_*.csv
  Plots: compare_cycle_time_fixed_bucket.svg, by_month.svg, scatter.svg (vector)
  manifest.txt – suggests: diff *_python.csv *_sql.csv
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Run from repo root so src is importable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd
from src.git_ir import git_log
from src.calculators.cycle_time_by_commits_calculator import (
    calculate_time_deltas,
    commit_statistics,
    commit_statistics_normalized_by_month,
)
from src.calculators.sqlite_lake import SqliteLake

DEFAULT_OUT = "scripts/compare_output"
STATS_COLS = ["interval_start", "sum", "average", "p75", "std"]


def run_toy_repo():
    """Create a small toy repo and return (logs, cwd_restore). Caller restores cwd."""
    import tempfile
    from src.util.toy_repo import ToyRepoCreator

    tmp = tempfile.mkdtemp(prefix="compare_cycle_", dir=REPO_ROOT)
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp)
        trc = ToyRepoCreator(tmp)
        trc.create_custom_commits_single_author([1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22, 34, 35, 41, 49])
        logs = git_log()
        return logs, orig_cwd
    except Exception:
        os.chdir(orig_cwd)
        raise


def main():
    logging.getLogger().setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Compare Python vs SQL cycle-time: write CSVs + plots to output dir for diff/snapshot."
    )
    parser.add_argument("--toy", action="store_true", help="Use a toy repo (deterministic)")
    parser.add_argument("--repo-dir", metavar="DIR", help="Path to another git repo to analyze (default: cwd)")
    parser.add_argument("--out-dir", default=DEFAULT_OUT, help=f"Output directory for CSVs and plots (default: {DEFAULT_OUT})")
    parser.add_argument("--bucket-size", type=int, default=4, help="Bucket size for fixed-bucket stats")
    parser.add_argument("--no-plot", action="store_true", help="Skip generating plots")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir) if os.path.isabs(args.out_dir) else os.path.join(REPO_ROOT, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    if args.toy:
        logs, orig_cwd = run_toy_repo()
        try:
            run_comparison(logs, args.bucket_size, out_dir, args.no_plot)
        finally:
            os.chdir(orig_cwd)
    elif args.repo_dir:
        repo_dir = os.path.abspath(args.repo_dir)
        if not os.path.isdir(repo_dir):
            print(f"Not a directory: {repo_dir}", file=sys.stderr)
            sys.exit(1)
        orig_cwd = os.getcwd()
        try:
            os.chdir(repo_dir)
            logs = git_log()
            if not logs:
                print(f"No commits in {repo_dir}", file=sys.stderr)
                sys.exit(1)
            run_comparison(logs, args.bucket_size, out_dir, args.no_plot)
        finally:
            os.chdir(orig_cwd)
    else:
        logs = git_log()
        if not logs:
            print("No commits in current directory. Use --toy or --repo-dir DIR.", file=sys.stderr)
            sys.exit(1)
        run_comparison(logs, args.bucket_size, out_dir, args.no_plot)

    manifest_path = os.path.join(out_dir, "manifest.txt")
    write_manifest(out_dir, args.no_plot, manifest_path)
    print(out_dir)


def write_manifest(out_dir, no_plot, path):
    lines = [
        "Python vs SQL cycle-time comparison output.",
        "Compare with: diff <file>_python.csv <file>_sql.csv",
        "",
        "CSVs:",
        "  deltas_python.csv, deltas_sql.csv",
        "  fixed_bucket_python.csv, fixed_bucket_sql.csv",
        "  by_month_python.csv, by_month_sql.csv",
    ]
    if not no_plot:
        lines.extend([
            "",
            "Plots:",
            "  compare_cycle_time_fixed_bucket.svg",
            "  compare_cycle_time_by_month.svg",
            "  compare_cycle_time_scatter.svg",
        ])
    with open(path, "w") as f:
        f.write("\n".join(lines))


def run_comparison(logs, bucket_size, out_dir, no_plot):
    lake = SqliteLake()
    conn = lake.create_db()

    # --- Deltas ---
    py_deltas = calculate_time_deltas(logs)
    sql_deltas = lake.calculate_time_deltas_sql(conn, logs=logs)
    py_sorted = sorted(py_deltas, key=lambda x: (x[0], x[1]))
    sql_sorted = sorted(sql_deltas, key=lambda x: (x[0], x[1]))

    pd.DataFrame(py_sorted, columns=["committed_date", "cycle_minutes"]).to_csv(
        os.path.join(out_dir, "deltas_python.csv"), index=False
    )
    pd.DataFrame(sql_sorted, columns=["committed_date", "cycle_minutes"]).to_csv(
        os.path.join(out_dir, "deltas_sql.csv"), index=False
    )

    # --- Fixed-bucket stats ---
    py_fixed = commit_statistics(py_deltas, bucket_size=bucket_size)
    sql_fixed = lake.commit_statistics_sql(conn, bucket_size, logs=logs)
    pd.DataFrame(py_fixed, columns=STATS_COLS).to_csv(
        os.path.join(out_dir, "fixed_bucket_python.csv"), index=False
    )
    pd.DataFrame(sql_fixed, columns=STATS_COLS).to_csv(
        os.path.join(out_dir, "fixed_bucket_sql.csv"), index=False
    )

    # --- By-month stats ---
    py_month = commit_statistics_normalized_by_month(py_deltas)
    sql_month = lake.commit_statistics_normalized_by_month_sql(conn, logs=logs)
    pd.DataFrame(py_month, columns=STATS_COLS).to_csv(
        os.path.join(out_dir, "by_month_python.csv"), index=False
    )
    pd.DataFrame(sql_month, columns=STATS_COLS).to_csv(
        os.path.join(out_dir, "by_month_sql.csv"), index=False
    )

    if no_plot:
        return

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    w = 0.35
    x = range(len(py_fixed))

    # Fixed-bucket: sum + average
    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    axes[0].bar([i - w/2 for i in x], [r[1] for r in py_fixed], width=w, label="Python", color="C0")
    axes[0].bar([i + w/2 for i in x], [r[1] for r in sql_fixed], width=w, label="SQL", color="C1")
    axes[0].set_ylabel("Sum (minutes)")
    axes[0].set_title("Fixed-bucket: Sum – Python vs SQL")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([r[0] for r in py_fixed])
    axes[0].legend()

    axes[1].bar([i - w/2 for i in x], [r[2] for r in py_fixed], width=w, label="Python", color="C0")
    axes[1].bar([i + w/2 for i in x], [r[2] for r in sql_fixed], width=w, label="SQL", color="C1")
    axes[1].set_ylabel("Average (minutes)")
    axes[1].set_xlabel("Interval (YYYY-MM)")
    axes[1].set_title("Fixed-bucket: Average – Python vs SQL")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([r[0] for r in py_fixed])
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "compare_cycle_time_fixed_bucket.svg"), format="svg")
    plt.close(fig)

    # By-month: sum
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    xm = range(len(py_month))
    ax2.bar([i - w/2 for i in xm], [r[1] for r in py_month], width=w, label="Python sum", color="C0")
    ax2.bar([i + w/2 for i in xm], [r[1] for r in sql_month], width=w, label="SQL sum", color="C1")
    ax2.set_ylabel("Sum (minutes)")
    ax2.set_xlabel("Month")
    ax2.set_title("By-month: Sum – Python vs SQL")
    ax2.set_xticks(xm)
    ax2.set_xticklabels([r[0] for r in py_month])
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(os.path.join(out_dir, "compare_cycle_time_by_month.svg"), format="svg")
    plt.close(fig2)

    # Scatter: Python vs SQL
    all_py = [r[1] for r in py_fixed] + [r[2] for r in py_fixed] + [r[1] for r in py_month] + [r[2] for r in py_month]
    all_sql = [r[1] for r in sql_fixed] + [r[2] for r in sql_fixed] + [r[1] for r in sql_month] + [r[2] for r in sql_month]
    fig3, ax3 = plt.subplots(figsize=(5, 5))
    ax3.scatter(all_py, all_sql, alpha=0.7)
    mx = max(all_py + all_sql) * 1.05 or 1
    ax3.plot([0, mx], [0, mx], "k--", label="y=x (perfect match)")
    ax3.set_xlabel("Python value")
    ax3.set_ylabel("SQL value")
    ax3.set_title("Python vs SQL – points on diagonal = match")
    ax3.legend()
    ax3.set_aspect("equal")
    fig3.tight_layout()
    fig3.savefig(os.path.join(out_dir, "compare_cycle_time_scatter.svg"), format="svg")
    plt.close(fig3)


if __name__ == "__main__":
    main()
