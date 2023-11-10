from datetime import datetime
from io import StringIO
import time
from src.git_ir import all_objects, git_log, git_obj, format_git_logs_as_string
from src.util.git_util import git_run
from subprocess import run as sp_run
import numpy as np
from statistics import stdev
import logging

logging.basicConfig(
    level=logging.DEBUG,  # Set the desired log level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def cycle_time_between_commits_by_author(fname='a.csv', bucket_size=1000, window_size=250):
    """
    Calculate and analyze the cycle time between commits made by author to the main branch.

    This function retrieves Git commit data, calculates the time difference between commits by the same author,
    and then analyzes the cycle time, which is the time between consecutive commits by the same author.

    Args:
        fname (str, optional): The name of the output CSV file to save the analysis results. Defaults to 'a.csv'.
        bucket_size (int, optional): The size of the time buckets for grouping commits (in number of commits). 
                                     Defaults to 1000.
        window_size (int, optional): The size of the moving window for calculating percentiles and standard 
                                    deviation (in number of commits). Defaults to 250.

    Returns:
        str: A CSV-formatted string containing the analysis results, including the interval start date, 
             the 75th percentile cycle time (in minutes), and the standard deviation of cycle time.

    Example:
        >>> opposite_cycle_time('analysis_results.csv', bucket_size=500, window_size=100)
        'INTERVAL START, p75 CYCLE TIME (minutes), std CYCLE TIME\\n2023-09-01 00:00:00, 45, 15\\n...'
    """
    oo = git_obj.obj

    # head
    head = git_run('log').stdout.splitlines()[0].split()[1] 

    logs = git_log()

    logging.debug('======= logs =======: \n%s', logs)
    formatted_logs = format_git_logs_as_string(logs)
    logging.debug('======= formatted logs =======: \n%s', formatted_logs)

    objs = all_objects()
    logging.debug('======= objs =======: \n%s', objs)

    # Create author_map
    author_map = {}
    for c in logs:
        a_email = c._author[0]
        author_map.setdefault(a_email, []).append(c)

    # Calculate time deltas
    all_time_deltas = []
    all_time_deltas_with_date = []
    for a, commits in author_map.items():
        for i in range(len(commits) - 1):
            c = commits[i]
            cn = commits[i + 1]
            time_delta = datetime.fromtimestamp(c._when) - datetime.fromtimestamp(cn._when)
            delta_in_minutes = round((time_delta.days * 24 * 60) + (time_delta.total_seconds() / 60), 2)
            all_time_deltas.append(delta_in_minutes)
            all_time_deltas_with_date.append([c._when, delta_in_minutes])

    # Sort by date and create sublists
    all_time_deltas_with_date = sorted(all_time_deltas_with_date, key=lambda x: x[0])
    all_time_deltas_with_date_sublist = [all_time_deltas_with_date[i:i + bucket_size] for i in range(0, len(all_time_deltas_with_date), bucket_size)]

    # Calculate p75 and std deviation
    buf = StringIO()
    print("INTERVAL START, SUM, AVERAGE, p75 CYCLE TIME (minutes), std CYCLE TIME", file=buf)

    for sublist in all_time_deltas_with_date_sublist:
        if len(sublist) >= 2:
            print(time.ctime(sublist[0][0]), 
                  sum(item[1] for item in sublist),
                  round(sum(item[1] for item in sublist) / len(sublist), 2),
                  int(round(np.percentile([item[1] for item in sublist], 75), 0)), 
                  int(round(stdev([item[1] for item in sublist]), 0)),
                  sep=',', file=buf)

    if fname is None:
        print(buf.getvalue())
    else:
        with open(fname, 'wt') as fout:
            print(buf.getvalue(), file=fout)
        if fname.endswith('.csv'):
            sp_run(['open', fname])
    return buf.getvalue()