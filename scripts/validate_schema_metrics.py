#!/usr/bin/env python3
"""
Single entry: validate schema/metrics_*.sql materialization SELECTs vs Python (commits_export).

Exit 0 on match, 1 on mismatch, 2 on bad arguments.

Resolution order when choosing repos:
  1. --repos-file FILE
  2. --repo-dir DIR (repeat for multiple roots)
  3. If neither: use REPO_ROOT/local_schema_validation_repos.txt when it exists and lists paths (batch).
  4. Else: validate the current working directory once.

Optional positional REPO_DIR is merged with any ``--repo-dir`` values (after those flags, in order).

Writes a new timestamped detail log under REPO_ROOT each run
(local_schema_validation_run.detail.<UTC>.log) so local_schema_validation_run.detail.log
is never overwritten unless you pass --detail-log to that path. Use --no-detail-log to skip.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from subprocess import CalledProcessError
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# This script lives in scripts/ at repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPOS_FILE = str(REPO_ROOT / "local_schema_validation_repos.txt")
# Fixed name preserved between runs; default run uses _new_detail_log_path() instead.
LEGACY_DETAIL_LOG_NAME = "local_schema_validation_run.detail.log"


def _new_detail_log_path() -> str:
    """Unique path per run; does not clobber LEGACY_DETAIL_LOG_NAME or prior timestamped logs."""
    stem = str(REPO_ROOT / "local_schema_validation_run.detail")
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    candidate = f"{stem}.{utc}.log"
    if not os.path.exists(candidate):
        return candidate
    for i in range(1, 10000):
        candidate = f"{stem}.{utc}.{i}.log"
        if not os.path.exists(candidate):
            return candidate
    raise RuntimeError("could not allocate detail log filename")


_AUTO_DETAIL_LOG = object()

from git_calculator.git_ir import git_log
from git_calculator.util.git_util import get_repo_id
from git_calculator.calculators.sqlite_lake.schema_metrics import (
    ALL_METRICS,
    DEFAULT_P75_STD_TOL,
    DEFAULT_SUM_AVG_TOL,
    METRIC_ALL,
    METRIC_MULTI_REPO_AGGREGATE,
    OPT_IN_METRICS,
    RUNNABLE_METRICS,
    cycle_time_monthly_canonical_pair_for_logs,
    validate_multi_repo_aggregate_for_local_repo_paths,
    validate_schema_metrics_for_logs,
    validation_failure_footer,
    write_canonical_cycle_time_csv,
)


def _read_repos_file(path: str) -> list[str]:
    roots: list[str] = []
    base = os.path.dirname(os.path.abspath(path))
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            expanded = os.path.expanduser(line)
            if os.path.isabs(expanded):
                roots.append(expanded)
            else:
                roots.append(os.path.abspath(os.path.join(base, expanded)))
    return roots


def _run_multi_repo_aggregate_validation(
    args: argparse.Namespace,
    repo_dirs: List[str],
    repos_file: Optional[str],
) -> int:
    """
    One validation run: ``MultiRepoCalculator`` metrics per root, then aggregate table parity.
    """
    orig_cwd = os.getcwd()
    n = len(repo_dirs)
    if args.no_detail_log:
        detail_path = None
    elif args.detail_log is _AUTO_DETAIL_LOG:
        detail_path = _new_detail_log_path()
    else:
        detail_path = os.path.abspath(os.path.expanduser(args.detail_log))
    detail_f = None
    if detail_path:
        try:
            detail_f = open(detail_path, "w", encoding="utf-8")
        except OSError as exc:
            print(f"Warning: could not write detail log {detail_path}: {exc}", file=sys.stderr)

    def _detail(line: str) -> None:
        if detail_f:
            detail_f.write(line + "\n")
            detail_f.flush()

    def _log(msg: str, *, err: bool = False) -> None:
        _detail(msg)
        if args.quiet and not err:
            return
        print(msg, file=sys.stderr, flush=True)

    try:
        if detail_f:
            _detail(f"# started {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
            _detail(f"# git_calculator_root={REPO_ROOT}")
            _detail(f"# detail_log_path={detail_path}")
            _detail(f"# metric={METRIC_MULTI_REPO_AGGREGATE}")
            _detail(f"# repo_count={n} cwd={orig_cwd}")
            if repos_file:
                _detail(f"# repos_file={repos_file}")
            _detail("# command_line: " + " ".join(sys.argv))
            if not args.no_detail_audit:
                _detail(
                    "# audit: per-repo commit counts / series lengths; batch_id/cohort_id; "
                    "aggregate row count; # timing: git metric collection vs sqlite round-trip"
                )
            _detail("")

        _log(
            f"Schema metrics validation — metric={METRIC_MULTI_REPO_AGGREGATE}, repos={n}"
            + (f", list={repos_file}" if repos_file else "")
        )
        for i, d in enumerate(repo_dirs, start=1):
            _log(f"  {i}. {d}")

        bad = [d for d in repo_dirs if not os.path.isdir(d)]
        if bad:
            for d in bad:
                msg = f"Not a directory: {d}"
                _log(msg, err=True)
                print(msg, file=sys.stderr, flush=True)
            foot = validation_failure_footer()
            _detail(foot)
            print(foot, file=sys.stderr, flush=True)
            summary_bad = f"Summary: FAILED — {METRIC_MULTI_REPO_AGGREGATE} (invalid paths)"
            _detail(summary_bad)
            print(summary_bad, file=sys.stderr, flush=True)
            return 1

        _log(
            f"Computing per-repo metrics and validating {METRIC_MULTI_REPO_AGGREGATE} "
            f"for {n} repo root(s) in one batch…"
        )

        def _audit_line(line: str) -> None:
            _detail(f"      audit {METRIC_MULTI_REPO_AGGREGATE}: {line}")

        audit_cb = (
            _audit_line
            if detail_f and not args.no_detail_audit
            else None
        )
        err, collect_s, validate_s, agg_rows = validate_multi_repo_aggregate_for_local_repo_paths(
            repo_dirs,
            on_audit=audit_cb,
        )
        if detail_f:
            _detail(
                "# timing: "
                f"collect_git_metrics_s={collect_s:.3f} "
                f"aggregate_sqlite_compare_s={validate_s:.3f} "
                f"total_s={collect_s + validate_s:.3f} "
                f"aggregate_materialization_rows={agg_rows}"
            )
        if err:
            _detail(err)
            print(err, file=sys.stderr, flush=True)
            foot = validation_failure_footer()
            _detail(foot)
            print(foot, file=sys.stderr, flush=True)
            summary_fail = f"Summary: FAILED — {METRIC_MULTI_REPO_AGGREGATE} ({n} repo(s))"
            _detail(summary_fail)
            print(summary_fail, file=sys.stderr, flush=True)
            return 1

        if not args.quiet:
            _log(
                f"OK: {METRIC_MULTI_REPO_AGGREGATE} — aggregate table parity for {n} repo root(s) "
                f"({agg_rows} aggregate rows; {collect_s:.1f}s git + {validate_s:.1f}s sqlite)"
            )
        summary_ok = (
            f"Summary: passed — {METRIC_MULTI_REPO_AGGREGATE} OK ({n} repo(s), {agg_rows} rows)"
        )
        _detail(summary_ok)
        print(summary_ok, file=sys.stderr, flush=True)
        return 0
    finally:
        os.chdir(orig_cwd)
        if detail_f:
            detail_f.close()


def main() -> int:
    logging.getLogger().setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(
        description="Validate schema/metrics_*.sql materializations vs Python (ALL_METRICS).",
        epilog=(
            f"Metrics: {METRIC_ALL} (SQL parity: {', '.join(ALL_METRICS)}), "
            f"opt-in: {', '.join(OPT_IN_METRICS)}, "
            f"{METRIC_MULTI_REPO_AGGREGATE} (all resolved repo roots in one batch; same repo list rules). "
            "Default repo list: local_schema_validation_repos.txt at git_calculator root when present."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_dir_positional",
        nargs="?",
        default=None,
        metavar="REPO_DIR",
        help="Optional repo root (merged after any --repo-dir values)",
    )
    parser.add_argument(
        "--repo-dir",
        action="append",
        dest="repo_dirs",
        metavar="DIR",
        default=None,
        help=(
            "Git repo root; repeat for multiple repositories (mutually exclusive with --repos-file "
            "and default batch file)"
        ),
    )
    parser.add_argument(
        "--repos-file",
        metavar="FILE",
        help=(
            "Newline-separated repo roots (# comments). "
            "If omitted, local_schema_validation_repos.txt under git_calculator root is used when it lists paths."
        ),
    )
    parser.add_argument(
        "--metric",
        default=METRIC_ALL,
        help=(
            f"Metric id or '{METRIC_ALL}' (default). One of: {METRIC_ALL}, "
            f"{', '.join(RUNNABLE_METRICS)}, "
            f"{METRIC_MULTI_REPO_AGGREGATE}."
        ),
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        help="If set and metric includes cycle_time_monthly, write canonical cycle-time CSVs",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress/OK lines; still print skips, failures, and final summary (stderr)",
    )
    parser.add_argument(
        "--verbose-git",
        action="store_true",
        help="Print every git subprocess invocation (# $> git …); default is quieter progress only",
    )
    parser.add_argument(
        "--sum-avg-tol",
        type=float,
        default=DEFAULT_SUM_AVG_TOL,
        help=f"cycle_time_monthly sum/avg tolerance (default {DEFAULT_SUM_AVG_TOL})",
    )
    parser.add_argument(
        "--p75-std-tol",
        type=float,
        default=DEFAULT_P75_STD_TOL,
        help=f"cycle_time_monthly p75/std tolerance (default {DEFAULT_P75_STD_TOL})",
    )
    parser.add_argument(
        "--detail-log",
        metavar="PATH",
        nargs="?",
        const=str(REPO_ROOT / LEGACY_DETAIL_LOG_NAME),
        default=_AUTO_DETAIL_LOG,
        help=(
            "Write full run transcript. Default: new file each run "
            f"local_schema_validation_run.detail.<UTC>.log under git_calculator root "
            f"(does not overwrite {LEGACY_DETAIL_LOG_NAME}). "
            f"--detail-log alone: write that fixed path (truncate). "
            "--detail-log PATH: write PATH (truncate)."
        ),
    )
    parser.add_argument(
        "--no-detail-log",
        action="store_true",
        help="Do not write the detail log file",
    )
    parser.add_argument(
        "--no-detail-audit",
        action="store_true",
        help=(
            "When writing a detail log, omit per-metric audit lines "
            "(counts, month/week ranges) after each OK metric"
        ),
    )
    args = parser.parse_args()

    if args.verbose_git:
        os.environ.pop("GIT_CALCULATOR_SILENCE_GIT_RUN", None)
    else:
        os.environ["GIT_CALCULATOR_SILENCE_GIT_RUN"] = "1"

    repo_dirs_from_flag: List[str] = list(args.repo_dirs or [])
    repo_dir_positional = args.repo_dir_positional
    has_explicit_repos = bool(repo_dirs_from_flag) or bool(repo_dir_positional)

    if args.repos_file and has_explicit_repos:
        print("Use only one of --repos-file / --repo-dir / REPO_DIR positional.", file=sys.stderr)
        return 2

    repos_file = args.repos_file
    if not repos_file and not has_explicit_repos:
        if os.path.isfile(DEFAULT_REPOS_FILE):
            trial = _read_repos_file(DEFAULT_REPOS_FILE)
            if trial:
                repos_file = DEFAULT_REPOS_FILE

    repo_dirs: list[str] = []
    if repos_file:
        if not os.path.isfile(repos_file):
            print(f"Not a file: {repos_file}", file=sys.stderr)
            return 1
        repo_dirs = _read_repos_file(repos_file)
        if not repo_dirs:
            print(f"No repo paths in {repos_file} (add one root per line).", file=sys.stderr)
            return 1
    else:
        if repo_dirs_from_flag or repo_dir_positional:
            repo_dirs = []
            for p in repo_dirs_from_flag:
                repo_dirs.append(os.path.abspath(os.path.expanduser(p)))
            if repo_dir_positional:
                repo_dirs.append(os.path.abspath(os.path.expanduser(repo_dir_positional)))
        else:
            repo_dirs = [os.getcwd()]

    if args.metric == METRIC_MULTI_REPO_AGGREGATE:
        return _run_multi_repo_aggregate_validation(args, repo_dirs, repos_file)

    n = len(repo_dirs)
    orig_cwd = os.getcwd()
    if args.no_detail_log:
        detail_path = None
    elif args.detail_log is _AUTO_DETAIL_LOG:
        detail_path = _new_detail_log_path()
    else:
        detail_path = os.path.abspath(os.path.expanduser(args.detail_log))
    detail_f = None
    if detail_path:
        try:
            detail_f = open(detail_path, "w", encoding="utf-8")
        except OSError as exc:
            print(f"Warning: could not write detail log {detail_path}: {exc}", file=sys.stderr)

    def _detail(line: str) -> None:
        if detail_f:
            detail_f.write(line + "\n")
            detail_f.flush()

    def _log(msg: str, *, err: bool = False) -> None:
        _detail(msg)
        if args.quiet and not err:
            return
        # All progress on stderr so IDEs / tasks that only surface stderr still show output.
        print(msg, file=sys.stderr, flush=True)

    any_fail = False
    n_ok = 0
    n_skip = 0
    n_metric_fail = 0
    n_err = 0
    summary = ""
    summary_written = False
    try:
        if detail_f:
            _detail(f"# started {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
            _detail(f"# git_calculator_root={REPO_ROOT}")
            _detail(f"# detail_log_path={detail_path}")
            _detail(f"# metric={args.metric}")
            _detail(f"# repo_count={n} cwd={orig_cwd}")
            if repos_file:
                _detail(f"# repos_file={repos_file}")
            _detail(
                "# cycle_time_monthly tolerances (minutes): "
                f"sum_avg_tol={args.sum_avg_tol} "
                f"p75_std_tol={args.p75_std_tol} "
                f"(defaults from schema_metrics: {DEFAULT_SUM_AVG_TOL}/{DEFAULT_P75_STD_TOL})"
            )
            _detail(
                "# flags: "
                f"quiet={args.quiet} "
                f"verbose_git={args.verbose_git} "
                f"no_detail_audit={args.no_detail_audit} "
                f"no_detail_log={args.no_detail_log}"
            )
            _detail(f"# out_dir={args.out_dir!r}")
            _detail("# command_line: " + " ".join(sys.argv))
            if not args.no_detail_audit:
                _detail(
                    "# audit: after each OK metric, a line with row counts / time ranges "
                    "(use --no-detail-audit to omit)"
                )
            _detail("")

        _log(
            f"Schema metrics validation — metric={args.metric}, repos={n}"
            + (f", list={repos_file}" if repos_file else "")
        )
        for i, d in enumerate(repo_dirs, start=1):
            _log(f"  {i}. {d}")

        for i, repo_dir in enumerate(repo_dirs, start=1):
            if not os.path.isdir(repo_dir):
                _log(f"[{i}/{n}] SKIP (not a directory): {repo_dir}", err=True)
                any_fail = True
                n_skip += 1
                continue
            _log(f"[{i}/{n}] entering {repo_dir}", err=False)
            try:
                os.chdir(repo_dir)
                logs = git_log()
                if not logs:
                    _log(f"[{i}/{n}] SKIP (no commits): {repo_dir}", err=True)
                    any_fail = True
                    n_skip += 1
                    continue
                repo_slug = get_repo_id()
                _log(
                    f"[{i}/{n}] {repo_dir} … {len(logs)} commits, {repo_slug} … validating"
                )

                def _per_metric(mid: str, maybe_err: Optional[str]) -> None:
                    line = f"  {mid}: {'FAIL' if maybe_err else 'OK'}"
                    _log(line, err=bool(maybe_err))

                def _audit_to_detail(mid: str, audit_line: str) -> None:
                    _detail(f"      audit {mid}: {audit_line}")

                err = validate_schema_metrics_for_logs(
                    logs,
                    repo_slug,
                    args.metric,
                    sum_avg_tol=args.sum_avg_tol,
                    p75_std_tol=args.p75_std_tol,
                    per_metric=_per_metric,
                    on_metric_ok_audit=(
                        _audit_to_detail
                        if detail_f and not args.no_detail_audit
                        else None
                    ),
                )

                if args.out_dir and (
                    args.metric == METRIC_ALL or args.metric == "cycle_time_monthly"
                ):
                    out = Path(args.out_dir).resolve()
                    py_canon, sql_canon = cycle_time_monthly_canonical_pair_for_logs(
                        logs, repo_slug
                    )
                    write_canonical_cycle_time_csv(
                        out / "cycle_time_python_canonical.csv", py_canon
                    )
                    write_canonical_cycle_time_csv(
                        out / "cycle_time_schema_canonical.csv", sql_canon
                    )

                if err:
                    _log(f"[{i}/{n}] FAIL: {repo_dir}", err=True)
                    _detail(err)
                    foot = validation_failure_footer()
                    _detail(foot)
                    print(err, file=sys.stderr, flush=True)
                    print(foot, file=sys.stderr, flush=True)
                    any_fail = True
                    n_metric_fail += 1
                else:
                    n_ok += 1
                    _log(f"[{i}/{n}] OK: {repo_dir}")
            except CalledProcessError as e:
                any_fail = True
                n_skip += 1
                err_bits = e.stderr
                if isinstance(err_bits, bytes):
                    err_bits = err_bits.decode(errors="replace")
                err_text = (err_bits or str(e)).strip()
                msg = (
                    f"[{i}/{n}] SKIP (git failed): {repo_dir}\n"
                    f"  exit {e.returncode}: {err_text}"
                )
                _log(msg, err=True)
            except Exception:
                any_fail = True
                n_err += 1
                tb = traceback.format_exc()
                _log(f"[{i}/{n}] ERROR (exception): {repo_dir}", err=True)
                _detail(tb)
                print(tb, file=sys.stderr, flush=True)
            finally:
                os.chdir(orig_cwd)

        status = "FAILED" if any_fail else "passed"
        summary = (
            f"Summary: {status} — {n_ok} OK, {n_metric_fail} failed, {n_skip} skipped, "
            f"{n_err} exceptions (of {n} repo(s))"
        )
        _detail(summary)
        summary_written = True
    finally:
        os.chdir(orig_cwd)
        if detail_f:
            if not summary_written:
                status = "FAILED" if any_fail else "passed"
                summary = (
                    f"Summary: {status} — {n_ok} OK, {n_metric_fail} failed, {n_skip} skipped, "
                    f"{n_err} exceptions (of {n} repo(s)) [incomplete run]"
                )
                detail_f.write(summary + "\n")
            detail_f.close()

    print(summary if summary else "Summary: (no data)", file=sys.stderr, flush=True)

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
