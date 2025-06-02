from datetime import datetime
import logging
from src.git_ir import git_log, format_git_logs_as_string
from collections import defaultdict
from io import StringIO
from subprocess import run as sp_run
from src.util.git_util import git_run

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def extract_commit_data(logs):
    """
    Extract commit data and count commits containing specific keywords.

    Args:
        logs (list): List of commit logs.

    Returns:
        dict: Dictionary with months as keys and tuples (total commits, fix commits) as values.
    """
    data_by_month = defaultdict(lambda: (0, 0))
    keywords = {"revert", "hotfix", "bugfix", "bug", "fix", "problem", "issue"}

    for commit in logs:
        commit_date = datetime.fromtimestamp(commit._when)
        month_key = f"{commit_date.year}-{commit_date.month:02d}"
        total_commits, fix_commits = data_by_month[month_key]

        # Extract commit message
        commit_message = git_run('log', '-n', '1', '--format=%B', commit).stdout.strip().lower()

        # Check for keywords in commit message
        if any(keyword in commit_message for keyword in keywords):
            fix_commits += 1

        data_by_month[month_key] = (total_commits + 1, fix_commits)

    return data_by_month



def calculate_change_failure_rate(data_by_month):
    """
    Calculate the change failure rate per month.

    Args:
        data_by_month (dict): Dictionary with months as keys and tuples (total commits, fix commits) as values.

    Returns:
        dict: Dictionary with months as keys and change failure rates as values.
    """
    change_failure_rates = {}
    for month, (total_commits, fix_commits) in data_by_month.items():
        if total_commits > 0:
            rate = round((fix_commits / total_commits) * 100, 1)
        else:
            rate = 0
        change_failure_rates[month] = rate
    return change_failure_rates

def change_failure_rate_to_string(change_failure_rates):
    """
    Convert change failure rate statistics to a CSV-formatted string.

    Args:
        change_failure_rates (dict): Dictionary with months as keys and change failure rates as values.

    Returns:
        str: CSV-formatted string.
    """
    buf = StringIO()
    print("Month,Change Failure Rate (%)", file=buf)
    for month, rate in sorted(change_failure_rates.items()):
        print(f"{month},{rate:.2f}", file=buf)
    return buf.getvalue()

def write_change_failure_rate_to_file(change_failure_rates, fname='change_failure_rate_by_month.csv'):
    """
    Write the change failure rate statistics to a file.

    Args:
        change_failure_rates (dict): Dictionary with months as keys and change failure rates as values.
        fname (str): Filename for the output.
    """
    stats_string = change_failure_rate_to_string(change_failure_rates)
    with open(fname, 'wt') as fout:
        fout.write(stats_string)
    if fname.endswith('.csv'):
        sp_run(['open', fname])

def monthly_change_failure_analysis():
    """
    Main function to calculate and write monthly change failure rate statistics.
    """
    logs = git_log()
    logging.debug('Logs: %s', format_git_logs_as_string(logs))

    data_by_month = extract_commit_data(logs)
    change_failure_rates = calculate_change_failure_rate(data_by_month)
    write_change_failure_rate_to_file(change_failure_rates)

if __name__ == "__main__":
    monthly_change_failure_analysis()
