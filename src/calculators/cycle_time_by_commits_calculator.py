from datetime import datetime
from io import StringIO
import time
from src.git_ir import all_objects, git_log, git_obj
from src.util.git_util import git_run
from subprocess import run as sp_run
import numpy as np
from statistics import stdev


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

    # logs
    logs = git_log();

    # objs
    objs = all_objects()

    # list of commits for each unique author
    author_map = {}

    for c in logs:

        a_email = c._author[0]
        if a_email in author_map:
            author_map[a_email].append(c)
        else:
            # If it's not a list, create a new list with the existing value and the new value
            author_map[a_email] = [c]

    print(author_map)
    # iterate over the map and calculate opposite cycle time
    all_time_deltas = []
    # keep track of the time deltas and the commit date
    all_time_deltas_with_date = []
    for a in author_map:

        count = 1
        commit_list_length = len(author_map[a])
        for c in author_map[a]:
            
            # iterate over the commits
            # ignore the last item because there is nothing left to compare it to
            if count >= commit_list_length:
                continue

            # get the next commit 
            cn = author_map[a][count]
            # calculate the time delta
            time_delta = datetime.fromtimestamp(c._when) - datetime.fromtimestamp(cn._when)
            delta_in_minutes = round((time_delta.days * 24 * 60) + (time_delta.total_seconds() / 60),2)
            all_time_deltas.append(delta_in_minutes)
            all_time_deltas_with_date.append([c._when, delta_in_minutes])

            count += 1 

    # ---

    # sort by date




    # separate the all_time_deltas into buckets

    all_time_deltas_with_date_length = len(all_time_deltas_with_date)
    sublist_size = all_time_deltas_with_date_length // bucket_size
    all_time_deltas_with_date_sublist = []

    # sort the list by date
    all_time_deltas_with_date = sorted(all_time_deltas_with_date)

    # iterate through the original list and create sublists
    for i in range(0, all_time_deltas_with_date_length, sublist_size):
        sublist_date = all_time_deltas_with_date[i:i + sublist_size]
        all_time_deltas_with_date_sublist.append(sublist_date)

    # If there's a remainder, the last sublist may be smaller than sublist_size
    # You can include the remaining elements in the last sublist
    if len(all_time_deltas_with_date_sublist) < bucket_size and all_time_deltas_with_date_sublist % sublist_size != 0:
        last_sublist_date = all_time_deltas_with_date[len(all_time_deltas_with_date_sublist) * sublist_size:]
        all_time_deltas_with_date_sublist.append(last_sublist_date)


    # for each subset, calculate the p75 and the standard deviation
    # add these time series data with the date of the first commit in the subset
    # write as a row in the table the date, the P75 and the standard dev
    
    buf = StringIO()
    print("INTERVAL START, p75 CYCLE TIME (minutes), std CYCLE TIME", file=buf)
    # iterate over the subsets
    l_length = len(all_time_deltas_with_date_sublist)
    for i in range (0, l_length, 1):
        #calculate p75
        #print("all_time_deltas_with_date_sublist[i]: " + str(all_time_deltas_with_date_sublist))
        #print("all_time_deltas_sublist[i]: "+str(all_time_deltas_sublist[i]) )
        if len(all_time_deltas_with_date_sublist[i]) >= 2:
            print(time.ctime(all_time_deltas_with_date_sublist[i][0][0]), 
                  int(round(np.percentile([item[1] for item in all_time_deltas_with_date_sublist[i]], 75), 0)), 
                  int(round(stdev([item[1] for item in all_time_deltas_with_date_sublist[i]]), 0)),
                  sep=',', file=buf)

    if fname is None:
        print(buf.getvalue())
    else:
        with open(fname, 'wt') as fout:
            print(buf.getvalue(), file=fout)
        if fname.endswith('.csv'):
            sp_run(['open', fname])
    return buf.getvalue()