from datetime import datetime
from io import StringIO
from src.git_ir import git_log, format_git_logs_as_string
from subprocess import run as sp_run
import logging
from collections import defaultdict

logging.basicConfig(
    level=logging.DEBUG,  # Set the desired log level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def extract_authors(logs):
    """
    Extract unique authors from git logs.

    Args:
        logs (list): List of commit logs.

    Returns:
        dict: Dictionary with months as keys and sets of unique authors as values.
    """
    authors_by_month = defaultdict(set)
    for commit in logs:
        author_email = commit._author[0]
        commit_date = datetime.fromtimestamp(commit._when)
        month_key = f"{commit_date.year}-{commit_date.month}"
        authors_by_month[month_key].add(author_email)
    return authors_by_month


def monthly_author_statistics(authors_by_month):
    """
    Count unique authors per month.

    Args:
        authors_by_month (dict): Dictionary with months as keys and sets of unique authors as values.

    Returns:
        dict: Dictionary with months as keys and counts of unique authors as values.
    """
    return {month: len(authors) for month, authors in authors_by_month.items()}


def author_statistics_to_string(author_stats):
    """
    Convert author statistics to a CSV-formatted string.

    Args:
        author_stats (dict): Dictionary with months as keys and author counts as values.

    Returns:
        str: CSV-formatted string.
    """
    buf = StringIO()
    print("Month,Unique Authors", file=buf)
    for month, count in sorted(author_stats.items()):
        print(f"{month},{count}", file=buf)
    return buf.getvalue()


def write_monthly_author_statistics_to_file(author_stats, fname="authors_by_month.csv"):
    """
    Write the author statistics to a file.

    Args:
        author_stats (dict): Dictionary with months as keys and author counts as values.
        fname (str): Filename for the output.
    """
    stats_string = author_statistics_to_string(author_stats)
    with open(fname, "wt") as fout:
        fout.write(stats_string)
    if fname.endswith(".csv"):
        sp_run(["open", fname])


def monthly_active_developers():
    """
    Main function to calculate and write monthly active developers statistics.
    """
    logs = git_log()
    logging.debug("Logs: %s", format_git_logs_as_string(logs))

    authors_by_month = extract_authors(logs)
    author_stats = monthly_author_statistics(authors_by_month)
    write_monthly_author_statistics_to_file(author_stats)
