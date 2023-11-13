from datetime import datetime
import logging
from src.git_ir import git_log, format_git_logs_as_string
from collections import defaultdict
from io import StringIO
from subprocess import run as sp_run

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def extract_commits_and_authors(logs):
    """
    Extract commits and their authors from git logs.

    Args:
        logs (list): List of commit logs.

    Returns:
        dict: Dictionary with months as keys and tuples (set of authors, commit count) as values.
    """
    data_by_month = defaultdict(lambda: (set(), 0))
    for commit in logs:
        author_email = commit._author[0]
        commit_date = datetime.fromtimestamp(commit._when)
        month_key = f"{commit_date.year}-{commit_date.month}"
        authors_set, commit_count = data_by_month[month_key]
        authors_set.add(author_email)
        data_by_month[month_key] = (authors_set, commit_count + 1)
    return data_by_month

def calculate_throughput(data_by_month):
    """
    Calculate the number of commits per active unique developer per month.

    Args:
        data_by_month (dict): Dictionary with months as keys and tuples (set of authors, commit count) as values.

    Returns:
        dict: Dictionary with months as keys and throughput (commits per unique developer) as values.
    """
    throughput_stats = {}
    for month, (authors, commit_count) in data_by_month.items():
        if authors:
            throughput_stats[month] = commit_count / len(authors)
        else:
            throughput_stats[month] = 0
    return throughput_stats

def throughput_stats_to_string(throughput_stats):
    """
    Convert throughput statistics to a CSV-formatted string.

    Args:
        throughput_stats (dict): Dictionary with months as keys and throughput values as values.

    Returns:
        str: CSV-formatted string.
    """
    buf = StringIO()
    print("Month,Commits Per Unique Developer", file=buf)
    for month, throughput in sorted(throughput_stats.items()):
        print(f"{month},{throughput:.2f}", file=buf)
    return buf.getvalue()

def write_throughput_stats_to_file(throughput_stats, fname='throughput_by_month.csv'):
    """
    Write the throughput statistics to a file.

    Args:
        throughput_stats (dict): Dictionary with months as keys and throughput values as values.
        fname (str): Filename for the output.
    """
    stats_string = throughput_stats_to_string(throughput_stats)
    with open(fname, 'wt') as fout:
        fout.write(stats_string)
    if fname.endswith('.csv'):
        sp_run(['open', fname])

def monthly_throughput_analysis():
    """
    Main function to calculate and write monthly throughput statistics.
    """
    logs = git_log()
    logging.debug('Logs: %s', format_git_logs_as_string(logs))

    data_by_month = extract_commits_and_authors(logs)
    throughput_stats = calculate_throughput(data_by_month)
    write_throughput_stats_to_file(throughput_stats)

