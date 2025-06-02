import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from datetime import datetime
import numpy as np

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
    
    # Plot P75 cycle time
    plt.plot(df['Month'], df['p75'], 'o-', label='P75 Cycle Time', linewidth=2)
    
    # Add trendline
    z = np.polyfit(range(len(df)), df['p75'], 1)
    p = np.poly1d(z)
    trendline = p(range(len(df)))
    plt.plot(df['Month'], trendline, '--', label='Trendline', alpha=0.7)
    
    # Add trendline value annotation
    last_value = trendline[-1]
    plt.annotate(f'Trend: {last_value:.1f} days',
                xy=(df['Month'].iloc[-1], last_value),
                xytext=(10, 10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Add standard deviation as a shaded area
    plt.fill_between(df['Month'], 
                    df['p75'] - df['std'],
                    df['p75'] + df['std'],
                    alpha=0.2,
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
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
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
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot failure rate
    plt.plot(df['Month'], df['Rate'], 'o-', label='Change Failure Rate', linewidth=2, color='#e74c3c')
    
    # Add trendline
    z = np.polyfit(range(len(df)), df['Rate'], 1)
    p = np.poly1d(z)
    trendline = p(range(len(df)))
    plt.plot(df['Month'], trendline, '--', label='Trendline', alpha=0.7)
    
    # Add trendline value annotation at the last point of the trendline
    last_month = df['Month'].iloc[-1]
    last_value = trendline[-1]
    plt.annotate(f'Trend: {last_value:.1f}%',
                xy=(last_month, last_value),
                xytext=(10, 0),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Add a horizontal line at 10% (industry standard)
    plt.axhline(y=10, color='gray', linestyle=':', alpha=0.5, label='Industry Standard (10%)')
    
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
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

def generate_charts(cycle_time_data=None, failure_rate_data=None):
    """
    Generate charts for both metrics if data is provided.
    
    Args:
        cycle_time_data: List of tuples (month, sum, average, p75, std)
        failure_rate_data: List of tuples (month, rate)
    """
    if cycle_time_data:
        plot_cycle_time(cycle_time_data)
    if failure_rate_data:
        plot_change_failure_rate(failure_rate_data) 