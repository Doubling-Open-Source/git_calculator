import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import argparse
from src.calculators.chart_generator import setup_plot_style

def plot_work_categories(client_name, csv_filename=None, title=None):
    """Generate a stacked bar chart for work categories over time."""
    setup_plot_style()
    
    # Determine CSV path
    if csv_filename:
        csv_path = f'clients/{client_name}/{csv_filename}'
    else:
        csv_path = f'clients/{client_name}/{client_name}_work_categories.csv'
    
    # Read the CSV
    df = pd.read_csv(csv_path)
    
    # Convert Month to datetime
    df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
    
    # Auto-detect categories (exclude Month, Total)
    exclude_cols = ['Month', 'Total']
    categories = [col for col in df.columns if col not in exclude_cols]
    
    # Define colors to match the style of chart_generator.py
    # Using cohesive palette with better contrast
    colors = [
        '#5cb85c',  # Brighter green for "New Features"
        '#f0ad4e',  # Warmer orange for "Improve things"  
        '#5bc0de',  # Lighter blue for "Productivity"
        '#d9534f',  # Clear red for "KTLO"
        '#999999',  # Medium gray for "Uncategorized"
    ]
    
    # Create the plot using plt.figure like chart_generator
    plt.figure(figsize=(12, 6))
    
    # Prepare data for stacked bar chart
    bottom = np.zeros(len(df))
    
    for i, category in enumerate(categories):
        color = colors[i % len(colors)]  # Cycle through colors if more categories
        plt.bar(df['Month'], df[category], bottom=bottom, 
                label=category, color=color, width=20, alpha=0.6)  # Changed from 0.8 to 0.6
        bottom += df[category]
    
    # Customize the plot (matching chart_generator style)
    plt.title(title or f'Work Categories Distribution - {client_name.replace("_", " ").title()}', pad=20)
    plt.xlabel('Month')
    plt.ylabel('Percentage (%)')
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    
    # Format x-axis (exactly like chart_generator)
    plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    # Set y-axis to 0-100
    plt.ylim(0, 100)
    plt.yticks(np.arange(0, 101, 10))
    
    plt.tight_layout()
    
    # Save to client directory
    output_dir = f'clients/{client_name}/outputs'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'work_categories_chart.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate work category charts')
    parser.add_argument('client', help='Client name (folder name in clients/)')
    parser.add_argument('--csv', help='CSV filename (default: client_work_categories.csv)')
    parser.add_argument('--title', help='Custom chart title')
    
    args = parser.parse_args()
    plot_work_categories(args.client, args.csv, args.title)