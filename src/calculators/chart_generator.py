import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from datetime import datetime
import numpy as np
import json
import os
from src.util.git_util import git_run

def setup_plot_style():
    """Set up a modern, clean style for the plots"""
    plt.style.use('seaborn-v0_8')
    sns.set_palette("husl")
    plt.rcParams['figure.figsize'] = [12, 6]
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.alpha'] = 0.3
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['savefig.facecolor'] = 'white'
    plt.rcParams['savefig.edgecolor'] = 'white'

def ensure_metrics_dir():
    """
    Ensure the metrics directory exists.
    Returns the path to the metrics directory.
    """
    metrics_dir = os.path.join(os.getcwd(), 'metrics')
    os.makedirs(metrics_dir, exist_ok=True)
    return metrics_dir

def get_repo_name():
    """
    Get the repository name from git configuration.
    Returns the repository name or 'repo' if not found.
    """
    try:
        # Try to get the remote URL
        remote_url = git_run('config', '--get', 'remote.origin.url').stdout.strip()
        if remote_url:
            # Extract repo name from URL (handles both https and ssh formats)
            repo_name = os.path.basename(remote_url)
            # Remove .git extension if present
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            return repo_name
    except:
        pass
    
    # If remote URL not found, try to get the directory name
    try:
        repo_name = os.path.basename(os.getcwd())
        return repo_name
    except:
        return 'repo'

def save_metrics_data(cycle_time_data=None, failure_rate_data=None, prefix=None):
    """
    Save the calculated metrics data to CSV files.
    
    Args:
        cycle_time_data: List of tuples (month, sum, average, p75, std)
        failure_rate_data: List of tuples (month, rate)
        prefix: Optional prefix for the output files. If None, uses repo name.
    """
    metrics_dir = ensure_metrics_dir()
    if prefix is None:
        prefix = f"{get_repo_name()}_"
    
    if cycle_time_data:
        df = pd.DataFrame(cycle_time_data, columns=['Month', 'Sum', 'Average', 'p75', 'std'])
        df.to_csv(os.path.join(metrics_dir, f'{prefix}cycle_time_data.csv'), index=False)
    
    if failure_rate_data:
        df = pd.DataFrame(failure_rate_data, columns=['Month', 'Rate'])
        df.to_csv(os.path.join(metrics_dir, f'{prefix}change_failure_data.csv'), index=False)

def load_metrics_data(prefix=None):
    """
    Load the metrics data from CSV files.
    
    Args:
        prefix: Optional prefix for the input files. If None, uses repo name.
    
    Returns:
        tuple: (cycle_time_data, failure_rate_data) as lists of tuples
    """
    metrics_dir = ensure_metrics_dir()
    if prefix is None:
        prefix = f"{get_repo_name()}_"
    
    cycle_time_data = None
    failure_rate_data = None
    
    try:
        df = pd.read_csv(os.path.join(metrics_dir, f'{prefix}cycle_time_data.csv'))
        cycle_time_data = [tuple(x) for x in df.values]
    except FileNotFoundError:
        pass
    
    try:
        df = pd.read_csv(os.path.join(metrics_dir, f'{prefix}change_failure_data.csv'))
        failure_rate_data = [tuple(x) for x in df.values]
    except FileNotFoundError:
        pass
    
    return cycle_time_data, failure_rate_data

def plot_cycle_time(cycle_time_data, output_file='cycle_time_chart.png'):
    """
    Generate a chart for cycle time metrics with trendline.
    
    Args:
        cycle_time_data: List of tuples (month, sum, average, p75, std)
        output_file: Name of the output file
    """
    setup_plot_style()
    
    # Convert data to DataFrame
    df = pd.DataFrame(cycle_time_data, columns=['Month', 'Sum', 'Average', 'p75', 'std'])
    df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
    
    # Convert minutes to days
    df['p75'] = df['p75'] / (24 * 60)  # Convert minutes to days
    df['std'] = df['std'] / (24 * 60)  # Convert standard deviation to days
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot P75 cycle time with the same blue color as change failure rate
    plt.plot(df['Month'], df['p75'], 'o-', label='P75 Cycle Time', 
             linewidth=2, color='#4B8BBE',  # Muted blue
             markersize=6, markerfacecolor='white', markeredgewidth=1.5)
    
    # Add trendline with the same darker blue
    z = np.polyfit(range(len(df)), df['p75'], 1)
    p = np.poly1d(z)
    trendline = p(range(len(df)))
    plt.plot(df['Month'], trendline, '--', label='Trendline', 
             alpha=0.7, color='#2B5F8E')  # Darker blue
    
    # Add trendline value annotation
    last_value = trendline[-1]
    plt.annotate(f'Trend: {last_value:.1f} days',
                xy=(df['Month'].iloc[-1], last_value),
                xytext=(10, 10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='#FFE873', alpha=0.7),  # Softer yellow
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Add standard deviation as a shaded area with the same blue
    plt.fill_between(df['Month'], 
                    df['p75'] - df['std'],
                    df['p75'] + df['std'],
                    alpha=0.2,
                    color='#4B8BBE',  # Same as main line but with alpha
                    label='Standard Deviation')
    
    # Customize the plot
    plt.title('Cycle Time Trend (P75)', pad=20)
    plt.xlabel('Month')
    plt.ylabel('Cycle Time (days)')
    plt.legend()
    
    # Set y-axis ticks to increments of 5 days, starting from 0
    max_days = df['p75'].max()
    y_ticks = np.arange(0, max_days + 5, 5)
    plt.yticks(y_ticks)
    plt.ylim(bottom=0)  # Remove negative y-axis
    
    # Format x-axis to show all months
    plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save the plot
    metrics_dir = ensure_metrics_dir()
    plt.savefig(os.path.join(metrics_dir, output_file), dpi=300, bbox_inches='tight')
    plt.close()

def plot_change_failure_rate(failure_rate_data, output_file='change_failure_rate_chart.png'):
    """
    Generate a chart for change failure rate with trendline.
    
    Args:
        failure_rate_data: List of tuples (month, rate)
        output_file: Name of the output file
    """
    setup_plot_style()
    
    # Convert data to DataFrame
    df = pd.DataFrame(failure_rate_data, columns=['Month', 'Rate'])
    df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
    
    # Sort data chronologically
    df = df.sort_values('Month')
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot failure rate with a muted blue color
    plt.plot(df['Month'], df['Rate'], 'o-', label='Change Failure Rate', 
             linewidth=2, color='#4B8BBE',  # Muted blue
             markersize=6, markerfacecolor='white', markeredgewidth=1.5)
    
    # Add trendline with a slightly darker blue
    z = np.polyfit(range(len(df)), df['Rate'], 1)
    p = np.poly1d(z)
    trendline = p(range(len(df)))
    plt.plot(df['Month'], trendline, '--', label='Trendline', 
             alpha=0.7, color='#2B5F8E')  # Darker blue
    
    # Add trendline value annotation at the last point of the trendline
    last_month = df['Month'].iloc[-1]
    last_value = trendline[-1]
    plt.annotate(f'Trend: {last_value:.1f}%',
                xy=(last_month, last_value),
                xytext=(10, 0),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='#FFE873', alpha=0.7),  # Softer yellow
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Add a horizontal line at 10% (industry standard) with a neutral gray
    plt.axhline(y=10, color='#666666', linestyle=':', alpha=0.5, label='Industry Standard (10%)')
    
    # Customize the plot
    plt.title('Change Failure Rate Trend', pad=20)
    plt.xlabel('Month')
    plt.ylabel('Change Failure Rate (%)')
    plt.legend()
    
    # Set y-axis ticks to increments of 5%, starting from 0
    max_rate = max(df['Rate'].max(), 10)  # Ensure we include the industry standard line
    y_ticks = np.arange(0, max_rate + 5, 5)
    plt.yticks(y_ticks)
    plt.ylim(bottom=0)  # Remove negative y-axis
    
    # Format x-axis to show all months
    plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save the plot
    metrics_dir = ensure_metrics_dir()
    plt.savefig(os.path.join(metrics_dir, output_file), dpi=300, bbox_inches='tight')
    plt.close()

def generate_charts(cycle_time_data=None, failure_rate_data=None, save_data=False, prefix=None):
    """
    Generate charts for both metrics if data is provided.
    
    Args:
        cycle_time_data: List of tuples (month, sum, average, p75, std)
        failure_rate_data: List of tuples (month, rate)
        save_data: Whether to save the data to CSV files
        prefix: Optional prefix for the output files. If None, uses repo name.
    """
    if prefix is None:
        prefix = f"{get_repo_name()}_"
    
    if save_data:
        save_metrics_data(cycle_time_data, failure_rate_data, prefix)
    
    if cycle_time_data:
        plot_cycle_time(cycle_time_data, f'{prefix}cycle_time_chart.png')
    if failure_rate_data:
        plot_change_failure_rate(failure_rate_data, f'{prefix}change_failure_rate_chart.png') 