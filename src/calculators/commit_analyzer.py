from datetime import datetime, timedelta
from collections import defaultdict
import logging
import os
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from src.git_ir import git_log, format_git_logs_as_string
from src.calculators.chart_generator import setup_plot_style, ensure_metrics_dir

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def extract_commits_by_author(logs):
    """
    Extract commits grouped by author and date.

    Args:
        logs (list): List of commit logs.

    Returns:
        dict: Dictionary with authors as keys and lists of (date, count) tuples as values.
    """
    commits_by_author = defaultdict(list)
    current_date = None
    current_count = 0
    
    for commit in sorted(logs, key=lambda x: x._when):
        commit_date = datetime.fromtimestamp(commit._when)
        author_email = commit._author[0]
        
        # Group commits by week
        week_start = commit_date - timedelta(days=commit_date.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if current_date != week_start:
            if current_date is not None:
                commits_by_author[current_author].append((current_date, current_count))
            current_date = week_start
            current_count = 1
            current_author = author_email
        else:
            if current_author == author_email:
                current_count += 1
            else:
                commits_by_author[current_author].append((current_date, current_count))
                current_count = 1
                current_author = author_email
    
    # Add the last group
    if current_date is not None:
        commits_by_author[current_author].append((current_date, current_count))
    
    return commits_by_author

def calculate_percentiles(commits_by_author: Dict[str, List[Tuple[datetime, int]]]) -> Dict[str, float]:
    """
    Calculate commit percentiles for all authors.
    
    Args:
        commits_by_author: Dictionary with authors as keys and lists of (date, count) tuples as values.
    
    Returns:
        dict: Dictionary with authors as keys and their percentile ranks as values.
    """
    total_commits = {author: sum(count for _, count in commits) 
                    for author, commits in commits_by_author.items()}
    
    commit_values = list(total_commits.values())
    ranks = pd.Series(commit_values).rank(method='max')
    percentiles = {author: (rank / len(commit_values)) * 100 
                  for author, rank in zip(total_commits.keys(), ranks)}
    return percentiles

def plot_commit_trends(commits_by_author: Dict[str, List[Tuple[datetime, int]]], output_file: str = 'commit_trends.png'):
    """
    Generate a chart for commit trends.
    
    Args:
        commits_by_author: Dictionary with authors as keys and lists of (date, count) tuples as values.
        output_file: Name of the output file.
    """
    setup_plot_style()
    
    # Convert data to DataFrame
    all_data = []
    for author, commits in commits_by_author.items():
        for date, count in commits:
            all_data.append({
                'Date': date,
                'Commits': count,
                'Author': author
            })
    
    df = pd.DataFrame(all_data)
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot each author's commits
    for author in df['Author'].unique():
        author_data = df[df['Author'] == author]
        plt.plot(author_data['Date'], author_data['Commits'], 'o-', label=author,
                markersize=6, markerfacecolor='white', markeredgewidth=1.5)
    
    # Customize the plot
    plt.title('Commit Trends by Author', pad=20)
    plt.xlabel('Date')
    plt.ylabel('Number of Commits')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Format x-axis
    plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Save the plot
    metrics_dir = ensure_metrics_dir()
    plt.savefig(os.path.join(metrics_dir, output_file), dpi=300, bbox_inches='tight')
    plt.close()

def save_commit_data(commits_by_author: Dict[str, List[Tuple[datetime, int]]], prefix: str = 'commit_'):
    """
    Save commit data to CSV files.
    
    Args:
        commits_by_author: Dictionary with authors as keys and lists of (date, count) tuples as values.
        prefix: Prefix for output files.
    """
    metrics_dir = ensure_metrics_dir()
    
    # Save individual author data
    for author, commits in commits_by_author.items():
        df = pd.DataFrame({
            'Date': [date for date, _ in commits],
            'Commits': [count for _, count in commits]
        })
        df.to_csv(os.path.join(metrics_dir, f'{prefix}{author}_commits.csv'), index=False)
    
    # Save percentile data
    percentiles = calculate_percentiles(commits_by_author)
    df_percentiles = pd.DataFrame({
        'Author': list(percentiles.keys()),
        'Percentile': list(percentiles.values())
    })
    df_percentiles.to_csv(os.path.join(metrics_dir, f'{prefix}percentiles.csv'), index=False)

def analyze_commits():
    """
    Main function to analyze commits in the local repository.
    """
    try:
        # Get commit logs
        logs = git_log()
        logging.debug('Logs: %s', format_git_logs_as_string(logs))
        
        # Extract and process commit data
        commits_by_author = extract_commits_by_author(logs)
        
        # Generate and save visualizations
        plot_commit_trends(commits_by_author)
        
        # Save data to CSV files
        save_commit_data(commits_by_author)
        
        # Print percentiles
        percentiles = calculate_percentiles(commits_by_author)
        for author, percentile in sorted(percentiles.items(), key=lambda x: x[1], reverse=True):
            logging.info(f"{author}: {percentile:.2f}th percentile")
            
    except Exception as e:
        logging.error(f"Error analyzing commits: {str(e)}")
        raise

if __name__ == "__main__":
    analyze_commits() 