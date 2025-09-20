"""
Multi-Repository Chart Generator

This module provides functionality to generate comparative charts
across multiple Git repositories.
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np
import os
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import logging

from src.calculators.chart_generator import setup_plot_style, ensure_metrics_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MultiRepoChartGenerator:
    """
    Generates comparative charts for multiple repositories.
    """
    
    def __init__(self, output_dir: str = "multi_repo_charts"):
        """
        Initialize the multi-repository chart generator.
        
        Args:
            output_dir: Directory to save generated charts
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Define color palette for repositories
        self.colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
    
    def plot_cycle_time_comparison(self, 
                                 metrics: Dict[str, Dict[str, Any]], 
                                 filename: str = "cycle_time_comparison.png") -> str:
        """
        Generate a comparison chart for cycle time across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart
        """
        setup_plot_style()
        
        plt.figure(figsize=(14, 8))
        
        color_idx = 0
        for repo_name, repo_metrics in metrics.items():
            cycle_data = repo_metrics.get('cycle_time_data', [])
            if not cycle_data:
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(cycle_data, columns=['Month', 'Sum', 'Average', 'P75', 'Std'])
            df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
            
            # Convert minutes to days
            df['P75'] = df['P75'] / (24 * 60)
            df['Std'] = df['Std'] / (24 * 60)
            
            color = self.colors[color_idx % len(self.colors)]
            
            # Plot P75 cycle time with standard deviation shading
            plt.plot(df['Month'], df['P75'], 'o-', 
                    label=f'{repo_name} (P75)', 
                    linewidth=2, 
                    color=color,
                    markersize=4,
                    alpha=0.8)
            
            # Add standard deviation shading (positive direction only)
            plt.fill_between(df['Month'], 
                           df['P75'], 
                           df['P75'] + df['Std'],
                           alpha=0.2, 
                           color=color,
                           label=f'{repo_name} (+1σ)')
            
            # Add trendline
            if len(df) > 1:
                z = np.polyfit(range(len(df)), df['P75'], 1)
                p = np.poly1d(z)
                trendline = p(range(len(df)))
                plt.plot(df['Month'], trendline, '--', 
                        alpha=0.6, 
                        color=color,
                        linewidth=1)
                
                # Add trendline end value label
                end_value = trendline[-1]
                end_month = df['Month'].iloc[-1]
                plt.annotate(f'{end_value:.1f}d', 
                           xy=(end_month, end_value),
                           xytext=(5, 5), 
                           textcoords='offset points',
                           fontsize=8,
                           color=color,
                           alpha=0.8,
                           bbox=dict(boxstyle='round,pad=0.3', 
                                   facecolor='white', 
                                   alpha=0.7,
                                   edgecolor=color,
                                   linewidth=0.5))
            
            color_idx += 1
        
        plt.title('Cycle Time Comparison Across Repositories (P75)', pad=20, fontsize=14)
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Cycle Time (days)', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Generated cycle time comparison chart: {output_path}")
        return output_path
    
    def plot_failure_rate_comparison(self, 
                                   metrics: Dict[str, Dict[str, Any]], 
                                   filename: str = "failure_rate_comparison.png") -> str:
        """
        Generate a comparison chart for change failure rate across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart
        """
        setup_plot_style()
        
        plt.figure(figsize=(14, 8))
        
        color_idx = 0
        for repo_name, repo_metrics in metrics.items():
            failure_data = repo_metrics.get('failure_rate_data', [])
            if not failure_data:
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(failure_data, columns=['Month', 'Rate'])
            df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
            df = df.sort_values('Month')
            
            color = self.colors[color_idx % len(self.colors)]
            
            # Plot failure rate
            plt.plot(df['Month'], df['Rate'], 'o-', 
                    label=f'{repo_name}', 
                    linewidth=2, 
                    color=color,
                    markersize=4,
                    alpha=0.8)
            
            # Add trendline
            if len(df) > 1:
                z = np.polyfit(range(len(df)), df['Rate'], 1)
                p = np.poly1d(z)
                trendline = p(range(len(df)))
                plt.plot(df['Month'], trendline, '--', 
                        alpha=0.6, 
                        color=color,
                        linewidth=1)
            
            color_idx += 1
        
        # Add industry standard line
        plt.axhline(y=10, color='#666666', linestyle=':', alpha=0.5, label='Industry Standard (10%)')
        
        plt.title('Change Failure Rate Comparison Across Repositories', pad=20, fontsize=14)
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Change Failure Rate (%)', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Generated failure rate comparison chart: {output_path}")
        return output_path
    
    def plot_active_developers_comparison(self, 
                                        metrics: Dict[str, Dict[str, Any]], 
                                        filename: str = "active_developers_comparison.png") -> str:
        """
        Generate a comparison chart for active developers across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart
        """
        setup_plot_style()
        
        plt.figure(figsize=(14, 8))
        
        color_idx = 0
        for repo_name, repo_metrics in metrics.items():
            active_dev_data = repo_metrics.get('active_dev_data', [])
            if not active_dev_data:
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(active_dev_data, columns=['Month', 'Authors', 'Commits'])
            df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
            df = df.sort_values('Month')
            
            color = self.colors[color_idx % len(self.colors)]
            
            # Plot active developers
            plt.plot(df['Month'], df['Authors'], 'o-', 
                    label=f'{repo_name}', 
                    linewidth=2, 
                    color=color,
                    markersize=4,
                    alpha=0.8)
            
            color_idx += 1
        
        plt.title('Active Developers Comparison Across Repositories', pad=20, fontsize=14)
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Number of Active Developers', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Generated active developers comparison chart: {output_path}")
        return output_path
    
    def plot_throughput_comparison(self, 
                                 metrics: Dict[str, Dict[str, Any]], 
                                 filename: str = "throughput_comparison.png") -> str:
        """
        Generate a comparison chart for throughput across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart
        """
        setup_plot_style()
        
        plt.figure(figsize=(14, 8))
        
        color_idx = 0
        for repo_name, repo_metrics in metrics.items():
            throughput_data = repo_metrics.get('throughput_data', [])
            if not throughput_data:
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(throughput_data, columns=['Month', 'Authors', 'Commits'])
            df['Month'] = pd.to_datetime(df['Month'], format='%Y-%m')
            df = df.sort_values('Month')
            
            color = self.colors[color_idx % len(self.colors)]
            
            # Plot throughput
            plt.plot(df['Month'], df['Commits'], 'o-', 
                    label=f'{repo_name}', 
                    linewidth=2, 
                    color=color,
                    markersize=4,
                    alpha=0.8)
            
            color_idx += 1
        
        plt.title('Throughput Comparison Across Repositories', pad=20, fontsize=14)
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Number of Commits', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Generated throughput comparison chart: {output_path}")
        return output_path
    
    def plot_repository_summary(self, 
                              metrics: Dict[str, Dict[str, Any]], 
                              filename: str = "repository_summary.png") -> str:
        """
        Generate a summary chart comparing key metrics across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart
        """
        setup_plot_style()
        
        # Extract summary data
        repo_names = []
        total_commits = []
        total_authors = []
        avg_cycle_times = []
        avg_failure_rates = []
        
        for repo_name, repo_metrics in metrics.items():
            repo_names.append(repo_name)
            total_commits.append(repo_metrics.get('total_commits', 0))
            total_authors.append(repo_metrics.get('total_authors', 0))
            
            # Calculate average cycle time
            cycle_data = repo_metrics.get('cycle_time_data', [])
            if cycle_data:
                avg_cycle_time = sum(point[3] for point in cycle_data) / len(cycle_data) / (24 * 60)  # Convert to days
            else:
                avg_cycle_time = 0
            avg_cycle_times.append(avg_cycle_time)
            
            # Calculate average failure rate
            failure_data = repo_metrics.get('failure_rate_data', [])
            if failure_data:
                avg_failure_rate = sum(point[1] for point in failure_data) / len(failure_data)
            else:
                avg_failure_rate = 0
            avg_failure_rates.append(avg_failure_rate)
        
        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # Plot 1: Total Commits
        bars1 = ax1.bar(repo_names, total_commits, color=self.colors[:len(repo_names)])
        ax1.set_title('Total Commits by Repository', fontsize=12)
        ax1.set_ylabel('Number of Commits')
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom')
        
        # Plot 2: Total Authors
        bars2 = ax2.bar(repo_names, total_authors, color=self.colors[:len(repo_names)])
        ax2.set_title('Total Authors by Repository', fontsize=12)
        ax2.set_ylabel('Number of Authors')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom')
        
        # Plot 3: Average Cycle Time
        bars3 = ax3.bar(repo_names, avg_cycle_times, color=self.colors[:len(repo_names)])
        ax3.set_title('Average Cycle Time by Repository', fontsize=12)
        ax3.set_ylabel('Cycle Time (days)')
        ax3.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars3:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom')
        
        # Plot 4: Average Failure Rate
        bars4 = ax4.bar(repo_names, avg_failure_rates, color=self.colors[:len(repo_names)])
        ax4.set_title('Average Change Failure Rate by Repository', fontsize=12)
        ax4.set_ylabel('Failure Rate (%)')
        ax4.tick_params(axis='x', rotation=45)
        
        # Add industry standard line
        ax4.axhline(y=10, color='red', linestyle='--', alpha=0.7, label='Industry Standard (10%)')
        ax4.legend()
        
        # Add value labels on bars
        for bar in bars4:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        plt.suptitle('Repository Comparison Summary', fontsize=16, y=0.98)
        plt.tight_layout()
        
        # Save the plot
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Generated repository summary chart: {output_path}")
        return output_path
    
    def plot_throughput_per_active_dev_comparison(self, metrics: Dict[str, Dict[str, Any]], filename: str = "throughput_per_active_dev_comparison.png") -> str:
        """
        Plot throughput per active developer comparison across repositories.
        
        Args:
            metrics: Dict of repository metrics
            filename: Output filename
            
        Returns:
            Path to the generated chart file
        """
        setup_plot_style()
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(metrics)))
        
        for i, (repo_name, repo_metrics) in enumerate(metrics.items()):
            throughput_per_active_dev_data = repo_metrics.get('throughput_per_active_dev_data', [])
            
            if not throughput_per_active_dev_data:
                continue
                
            months = []
            throughput_per_dev = []
            
            # Sort the data chronologically by week
            def week_sort_key(item):
                week_str = item[0]
                year, week_num = week_str.split('-W')
                return (int(year), int(week_num))
            
            sorted_data = sorted(throughput_per_active_dev_data, key=week_sort_key)
            
            for week, commits, active_dev_count, throughput_per_dev_val in sorted_data:
                # Convert ISO week format (2023-W01) to datetime
                year, week_num = week.split('-W')
                year = int(year)
                week_num = int(week_num)
                # Get the Monday of the week using fromisocalendar
                week_date = datetime.fromisocalendar(year, week_num, 1)
                months.append(week_date)
                throughput_per_dev.append(throughput_per_dev_val)
            
            if months:
                ax.plot(months, throughput_per_dev, 'o-', 
                       label=f'{repo_name}', 
                       linewidth=2, 
                       color=colors[i],
                       markersize=4,
                       alpha=0.8)
        
        ax.set_title('Throughput Per Active Developer Comparison Across Repositories (Weekly)', pad=20, fontsize=14)
        ax.set_xlabel('Week', fontsize=12)
        ax.set_ylabel('Commits Per Active Developer Per Week', fontsize=12)
        ax.tick_params(axis='x', rotation=45)
        ax.legend(title='Repository', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)
        
        plt.tight_layout()
        
        filepath = os.path.join(self.output_dir, filename)
        fig.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        logger.info(f"Generated throughput per active developer comparison chart: {filepath}")
        return filepath
    
    def generate_all_comparison_charts(self, metrics: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Generate all comparison charts for the given metrics.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of paths to generated chart files
        """
        generated_charts = []
        
        try:
            # Cycle time comparison
            chart_path = self.plot_cycle_time_comparison(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate cycle time comparison chart: {e}")
        
        try:
            # Failure rate comparison
            chart_path = self.plot_failure_rate_comparison(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate failure rate comparison chart: {e}")
        
        try:
            # Active developers comparison
            chart_path = self.plot_active_developers_comparison(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate active developers comparison chart: {e}")
        
        try:
            # Throughput comparison
            chart_path = self.plot_throughput_comparison(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate throughput comparison chart: {e}")
        
        try:
            # Throughput per active developer comparison
            chart_path = self.plot_throughput_per_active_dev_comparison(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate throughput per active developer comparison chart: {e}")
        
        try:
            # Repository summary
            chart_path = self.plot_repository_summary(metrics)
            generated_charts.append(chart_path)
        except Exception as e:
            logger.error(f"Failed to generate repository summary chart: {e}")
        
        logger.info(f"Generated {len(generated_charts)} comparison charts in {self.output_dir}")
        return generated_charts
