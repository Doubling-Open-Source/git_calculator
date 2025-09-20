from datetime import datetime, timedelta
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

def extract_commits_and_authors_by_week(logs):
    """
    Extract commits and their authors from git logs, grouped by week.

    Args:
        logs (list): List of commit logs.

    Returns:
        dict: Dictionary with weeks as keys and tuples (set of authors, commit count) as values.
    """
    data_by_week = defaultdict(lambda: (set(), 0))
    for commit in logs:
        author_email = commit._author[0]
        commit_date = datetime.fromtimestamp(commit._when)
        # Get the Monday of the week (ISO week)
        week_start = commit_date - timedelta(days=commit_date.weekday())
        week_key = f"{week_start.year}-W{week_start.isocalendar()[1]:02d}"
        authors_set, commit_count = data_by_week[week_key]
        authors_set.add(author_email)
        data_by_week[week_key] = (authors_set, commit_count + 1)
    return data_by_week

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

def get_active_developers(logs, weeks_back=4):
    """
    Get developers who have made commits in the past N weeks.
    
    Args:
        logs (list): List of commit logs.
        weeks_back (int): Number of weeks to look back for active developers.
        
    Returns:
        set: Set of active developer email addresses.
    """
    cutoff_date = datetime.now() - timedelta(weeks=weeks_back)
    active_developers = set()
    
    for commit in logs:
        commit_date = datetime.fromtimestamp(commit._when)
        if commit_date >= cutoff_date:
            author_email = commit._author[0]
            active_developers.add(author_email)
    
    return active_developers

def calculate_throughput_per_active_developer(logs, weeks_back=4):
    """
    Calculate throughput normalized by active developers (those who committed in past N weeks from each month).
    
    Args:
        logs (list): List of commit logs.
        weeks_back (int): Number of weeks to look back for active developers.
        
    Returns:
        dict: Dictionary with months as keys and tuples (commits, active_dev_count, throughput_per_active_dev) as values.
    """
    # Extract commits by month
    data_by_month = extract_commits_and_authors(logs)
    
    # Calculate normalized throughput for each month
    normalized_throughput = {}
    for month, (authors, commit_count) in data_by_month.items():
        # For each month, find developers who were active in the past N weeks from that month
        month_year, month_num = month.split('-')
        month_date = datetime(int(month_year), int(month_num), 1)
        cutoff_date = month_date - timedelta(weeks=weeks_back)
        
        # Find developers who committed in the past N weeks from this month
        active_developers_for_month = set()
        for commit in logs:
            commit_date = datetime.fromtimestamp(commit._when)
            if commit_date >= cutoff_date and commit_date <= month_date:
                author_email = commit._author[0]
                active_developers_for_month.add(author_email)
        
        # Count how many of the authors in this month are active developers
        active_authors_in_month = len(authors.intersection(active_developers_for_month))
        
        if active_authors_in_month > 0:
            throughput_per_active_dev = commit_count / active_authors_in_month
        else:
            throughput_per_active_dev = 0
            
        normalized_throughput[month] = (commit_count, active_authors_in_month, throughput_per_active_dev)
    
    return normalized_throughput

def calculate_throughput_per_active_developer_by_week(logs, weeks_back=4):
    """
    Calculate throughput normalized by active developers, grouped by week.
    
    Args:
        logs (list): List of commit logs.
        weeks_back (int): Number of weeks to look back for active developers.
        
    Returns:
        dict: Dictionary with weeks as keys and tuples (commits, active_dev_count, throughput_per_active_dev) as values.
    """
    # Extract commits by week
    data_by_week = extract_commits_and_authors_by_week(logs)
    
    # Calculate normalized throughput for each week
    normalized_throughput = {}
    for week, (authors, commit_count) in data_by_week.items():
        # For each week, find developers who were active in the past N weeks from that week
        year, week_num = week.split('-W')
        year = int(year)
        week_num = int(week_num)
        
        # Convert ISO week to date (Monday of that week)
        week_date = datetime.strptime(f"{year}-W{week_num:02d}-1", "%Y-W%W-%w")
        cutoff_date = week_date - timedelta(weeks=weeks_back)
        
        # Find developers who committed in the past N weeks from this week
        active_developers_for_week = set()
        for commit in logs:
            commit_date = datetime.fromtimestamp(commit._when)
            if commit_date >= cutoff_date and commit_date <= week_date + timedelta(days=7):
                author_email = commit._author[0]
                active_developers_for_week.add(author_email)
        
        # Count how many of the authors in this week are active developers
        active_authors_in_week = len(authors.intersection(active_developers_for_week))
        
        if active_authors_in_week > 0:
            throughput_per_active_dev = commit_count / active_authors_in_week
        else:
            throughput_per_active_dev = 0
            
        normalized_throughput[week] = (commit_count, active_authors_in_week, throughput_per_active_dev)
    
    return normalized_throughput

def monthly_throughput_analysis():
    """
    Main function to calculate and write monthly throughput statistics.
    """
    logs = git_log()
    logging.debug('Logs: %s', format_git_logs_as_string(logs))

    data_by_month = extract_commits_and_authors(logs)
    throughput_stats = calculate_throughput(data_by_month)
    write_throughput_stats_to_file(throughput_stats)

