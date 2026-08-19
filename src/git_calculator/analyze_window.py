"""UTC windowed analyze at weekly or monthly grain (SQL lake)."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from statistics import stdev
from typing import Any, Optional

import numpy as np

from git_calculator.calculators.sqlite_lake import SqliteLake
from git_calculator.calculators.sqlite_lake.commits_export_keywords import (
    text_has_change_failure_keyword,
)
from git_calculator.git_ir import git_log
from git_calculator.util.git_util import get_repo_id, get_repo_name
from git_calculator.work_style import SQUASH, require_known

WEEKLY = "weekly"
MONTHLY = "monthly"
KNOWN_GRAINS = frozenset({WEEKLY, MONTHLY})


def require_grain(grain: str) -> str:
    if grain not in KNOWN_GRAINS:
        raise ValueError(f"Unknown grain {grain!r}")
    return grain


def parse_utc_instant(value: str, *, label: str) -> datetime:
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{label} is not RFC3339 UTC: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _period_start(moment: datetime, grain: str) -> datetime:
    utc = moment.astimezone(timezone.utc).replace(microsecond=0)
    if grain == WEEKLY:
        midnight = utc.replace(hour=0, minute=0, second=0)
        return midnight - timedelta(days=midnight.weekday())
    return utc.replace(day=1, hour=0, minute=0, second=0)


def _next_period(start: datetime, grain: str) -> datetime:
    if grain == WEEKLY:
        return start + timedelta(days=7)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def _period_key(start: datetime, grain: str) -> str:
    if grain == WEEKLY:
        iso = start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{start.year:04d}-{start.month:02d}"


def _periods_overlapping(
    window_start: datetime, window_end: datetime, grain: str
) -> list[tuple[str, datetime, datetime]]:
    cursor = _period_start(window_start, grain)
    periods: list[tuple[str, datetime, datetime]] = []
    while cursor < window_end:
        end = _next_period(cursor, grain)
        periods.append((_period_key(cursor, grain), cursor, end))
        cursor = end
    return periods


def _fix_text(message: Optional[str], work_style: str) -> str:
    if not message:
        return ""
    if work_style == SQUASH:
        return message.split("\n", 1)[0]
    return message


def _hours(minutes: float) -> float:
    return round(minutes / 60.0, 2)


def _cycle_stats(minutes: list[float]) -> dict[str, Any]:
    count = len(minutes)
    if count == 0:
        return {
            "cycle_time_samples": 0,
            "cycle_time_avg_hours": None,
            "cycle_time_p75_hours": None,
            "cycle_time_stddev_hours": None,
        }
    return {
        "cycle_time_samples": count,
        "cycle_time_avg_hours": _hours(sum(minutes) / count),
        "cycle_time_p75_hours": _hours(float(np.percentile(minutes, 75))),
        "cycle_time_stddev_hours": _hours(stdev(minutes)) if count >= 2 else None,
    }


def analyze_window(
    repo_path: str,
    window_start: datetime,
    window_end: datetime,
    grain: str,
    backend: str = "sql",
    work_style: str = "all-branches",
    default_branch: Optional[str] = None,
) -> list[dict[str, Any]]:
    require_grain(grain)
    require_known(work_style)
    if backend != "sql":
        raise ValueError("windowed analyze requires --backend sql")
    if (
        window_start.tzinfo is None
        or window_end.tzinfo is None
        or window_start.utcoffset() != timedelta(0)
        or window_end.utcoffset() != timedelta(0)
    ):
        raise ValueError("--from and --to must be UTC")
    start = window_start.astimezone(timezone.utc)
    end = window_end.astimezone(timezone.utc)
    if start >= end:
        raise ValueError("--from must be strictly before --to")

    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    original_cwd = os.getcwd()
    lake: Optional[SqliteLake] = None
    try:
        os.chdir(repo_path)
        logs = git_log(work_style=work_style, default_branch=default_branch)
        lake = SqliteLake()
        repo_id = get_repo_id()
        lake.load_logs(logs, repo_id)
        deltas = lake.calculate_time_deltas_sql(repo_id)
        commit_rows = lake.conn.execute(
            "SELECT committed_date, message FROM commits WHERE _raw_data_params = ?",
            (repo_id,),
        ).fetchall()
    finally:
        if lake is not None:
            lake.close()
        os.chdir(original_cwd)

    commits_by_period: dict[str, list[bool]] = {
        key: [] for key, _, _ in _periods_overlapping(start, end, grain)
    }
    minutes_by_period: dict[str, list[float]] = {
        key: [] for key in commits_by_period
    }

    for committed_date, message in commit_rows:
        if not (start_ts <= int(committed_date) < end_ts):
            continue
        moment = datetime.fromtimestamp(int(committed_date), tz=timezone.utc)
        key = _period_key(_period_start(moment, grain), grain)
        if key not in commits_by_period:
            continue
        text = _fix_text(message, work_style)
        commits_by_period[key].append(
            bool(text) and text_has_change_failure_keyword(text)
        )

    for committed_date, minutes in deltas:
        if not (start_ts <= int(committed_date) < end_ts):
            continue
        moment = datetime.fromtimestamp(int(committed_date), tz=timezone.utc)
        key = _period_key(_period_start(moment, grain), grain)
        if key not in minutes_by_period:
            continue
        minutes_by_period[key].append(float(minutes))

    series: list[dict[str, Any]] = []
    for key, period_start, period_end in _periods_overlapping(start, end, grain):
        flags = commits_by_period[key]
        commits = len(flags)
        fix_commits = sum(1 for is_fix in flags if is_fix)
        rate = round(100.0 * fix_commits / commits, 1) if commits else None
        series.append(
            {
                "period": key,
                "period_start": period_start,
                "period_end": period_end,
                "commits": commits,
                "fix_commits": fix_commits,
                "change_failure_rate_pct": rate,
                **_cycle_stats(minutes_by_period[key]),
            }
        )
    return series


def write_window_series_csv(series: list[dict[str, Any]], path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fields = [
        "period",
        "period_start",
        "period_end",
        "commits",
        "fix_commits",
        "change_failure_rate_pct",
        "cycle_time_avg_hours",
        "cycle_time_p75_hours",
        "cycle_time_samples",
        "cycle_time_stddev_hours",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in series:
            out = dict(row)
            for key in ("period_start", "period_end"):
                value = out.get(key)
                if isinstance(value, datetime):
                    out[key] = value.astimezone(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
            writer.writerow(out)


def window_series_csv_path(repo_path: str, output_dir: str) -> str:
    original_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        name = get_repo_name()
    finally:
        os.chdir(original_cwd)
    return os.path.join(repo_path, output_dir, f"{name}_sql_window_series.csv")
