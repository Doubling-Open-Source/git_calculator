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


def calculate_time_deltas(logs):
    """
    Calculate time deltas between commits for each author.

    Args:
        logs (list): List of commit logs.

    Returns:
        list: List of time deltas with dates.
    """
    author_map = {}
    for commit in logs:
        a_email = commit._author[0]
        author_map.setdefault(a_email, []).append(commit)

    time_deltas = []
    for author, commits in author_map.items():
        for i in range(len(commits) - 1):
            current_commit = commits[i]
            next_commit = commits[i + 1]
            time_delta = datetime.fromtimestamp(current_commit._when) - datetime.fromtimestamp(next_commit._when)
            delta_in_minutes = round((time_delta.days * 24 * 60) + (time_delta.seconds / 60), 2)
            time_deltas.append([current_commit._when, delta_in_minutes])
    return time_deltas

def commit_statistics(time_deltas, bucket_size):
    """
    Statistics about commit times.

    Args:
        time_deltas (list): List of time deltas with dates.
        bucket_size (int): Size of each bucket for grouping time deltas.
    """
    sorted_deltas = sorted(time_deltas, key=lambda x: x[0])
    delta_sublists = [sorted_deltas[i:i + bucket_size] for i in range(0, len(sorted_deltas), bucket_size)]
    return_value = []

    for sublist in delta_sublists:
        if len(sublist) >= 2:
            s_start_time = time.ctime(sublist[0][0])
            s_sum = sum(item[1] for item in sublist)
            s_average = round(sum(item[1] for item in sublist) / len(sublist), 2)
            s_p75 = int(round(np.percentile([item[1] for item in sublist], 75), 0))
            s_std = int(round(stdev([item[1] for item in sublist]), 0))
            return_value.append((s_start_time, s_sum, s_average, s_p75, s_std))

    return return_value

def commit_statistics_normalized_by_month(time_deltas):
    """
    Statistics about commit cycle times, where each set of data is 
    normalized by the commits in a given month.

    Args:
        time_deltas (list): List of time deltas with dates.
    """
    sorted_deltas = sorted(time_deltas, key=lambda x: x[0])
    # find the first date in the list
    first_date = sorted_deltas[0][0]
    # create a list of to hold each month
    month_buckets = []
    current_month = None

    # iterate through sorted_deltas and assign each to the appropriate month in month_buckets
    for delta in sorted_deltas:
        logging.debug('======= delta =======: \n%s', delta)
        month_year = (datetime.fromtimestamp(delta[0]).year, datetime.fromtimestamp(delta[0]).month)
        logging.debug('======= month_year =======: \n%s', month_year)
        if month_year != current_month:
            current_month = month_year
            month_buckets.append([current_month])
            month_buckets[-1].append([])
        month_buckets[-1][1].append(delta)
    
    logging.debug('======= month_buckets =======: \n%s', month_buckets)
    return_value = []

    sample = [
            [(2023, 9), 
               [[1694502000, 1440.0], 
                [1694588400, 1440.0], 
                [1694674800, 1440.0]]], 
            [(2023, 10), 
                [[1696489200, 30240.0], 
                 [1696575600, 1440.0], 
                 [1697094000, 8640.0], 
                 [1697785200, 11520.0], 
                 [1698735600, 15840.0]]], 
            [(2023, 11), 
                [[1700035200, 21600.0], 
                 [1700467200, 7200.0], 
                 [1700899200, 7200.0]]]]

    for m in month_buckets:
        logging.debug('======= m =======: \n%s', m)
        if len(m[1]) >= 2:
            s_start_time = m[0]  # First data point's timestamp
            logging.debug('======= s_start_time =======: \n%s', s_start_time)
            s_sum = sum(item[1] for item in m[1]) # Summing the second elements of the sub-items
            logging.debug('======= s_sum =======: \n%s', s_sum)
            s_average = round(s_sum / len(m[1]), 2)
            logging.debug('======= s_average =======: \n%s', s_average)
            s_p75 = int(round(np.percentile([item[1] for item in m[1]], 75), 0))
            logging.debug('======= s_p75 =======: \n%s', s_p75)
            s_std = int(round(stdev([item[1] for item in m[1]]), 0))
            logging.debug('======= s_std =======: \n%s', s_std)
            return_value.append((s_start_time, s_sum, s_average, s_p75, s_std))

    return return_value

def commit_statistics_to_string(time_deltas, bucket_size):

    bucket_stats = commit_statistics(time_deltas, bucket_size)
    buf = StringIO()
    print("INTERVAL START, SUM, AVERAGE, p75 CYCLE TIME (minutes), std CYCLE TIME", file=buf)
    for s in bucket_stats:    
        print(s[0], 
            s[1],
            s[2],
            s[3], 
            s[4],
            sep=',', file=buf)
    return buf.getvalue()


def write_commit_statistics_to_file(time_deltas, bucket_size, fname='a.csv'):

    buf = commit_statistics(time_deltas, bucket_size)
    with open(fname, 'wt') as fout:
        print(buf.getvalue(), file=fout)
    if fname.endswith('.csv'):
        sp_run(['open', fname])


def cycle_time_between_commits_by_author(bucket_size=1000):
    """
    Calculate and analyze the cycle time between commits made by author to the main branch.

    Args:
        fname (str, optional): The name of the output CSV file to save the analysis results. Defaults to 'a.csv'.
        bucket_size (int, optional): The size of the time buckets for grouping commits. Defaults to 1000.
        window_size (int, optional): The size of the moving window for calculating percentiles and standard deviation. Defaults to 250.

    Returns:
        str: A CSV-formatted string containing the analysis results.
    """
    logs = git_log()
    logging.debug('======= logs =======: \n%s', logs)
    
    formatted_logs = format_git_logs_as_string(logs)
    logging.debug('======= formatted logs =======: \n%s', formatted_logs)

    time_deltas = calculate_time_deltas(logs)
    statistics = commit_statistics(time_deltas, bucket_size)

    return statistics



""" def cycle_time_between_commits_by_author(fname='a.csv', bucket_size=1000, window_size=250):
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
"""