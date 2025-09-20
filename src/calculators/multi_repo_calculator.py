"""
Multi-Repository Calculator

This module provides functionality to calculate and aggregate metrics
across multiple Git repositories for comparative analysis.
"""

import os
import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import pandas as pd
from datetime import datetime
import json

from src.multi_repo_manager import MultiRepoManager, RepositoryInfo
from src.git_ir import git_log
from src.calculators import (
    cycle_time_by_commits_calculator as cycle_calc,
    change_failure_calculator as cfc,
    active_developers_calculator as adc,
    throughput_calculator as tc,
    commit_analyzer as ca
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MultiRepoCalculator:
    """
    Calculates and aggregates metrics across multiple repositories.
    """
    
    def __init__(self, repo_manager: MultiRepoManager):
        """
        Initialize the multi-repository calculator.
        
        Args:
            repo_manager: MultiRepoManager instance with repositories to analyze
        """
        self.repo_manager = repo_manager
        self.metrics_cache: Dict[str, Dict[str, Any]] = {}
        
    def calculate_repo_metrics(self, repo_name: str) -> Dict[str, Any]:
        """
        Calculate all metrics for a single repository.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            Dict containing all calculated metrics
        """
        if repo_name in self.metrics_cache:
            logger.info(f"Using cached metrics for repository '{repo_name}'")
            return self.metrics_cache[repo_name]
        
        logger.info(f"Calculating metrics for repository '{repo_name}'")
        
        try:
            with self.repo_manager.repository_context(repo_name):
                # Get git logs
                logs = git_log()
                
                # Calculate cycle time metrics
                time_deltas = cycle_calc.calculate_time_deltas(logs)
                cycle_time_data = cycle_calc.commit_statistics_normalized_by_month(time_deltas)
                
                # Calculate change failure rate
                data_by_month = cfc.extract_commit_data(logs)
                failure_rate_data = [(month, rate) for month, rate in cfc.calculate_change_failure_rate(data_by_month).items()]
                
                # Calculate active developers
                authors_by_month = adc.extract_authors(logs)
                active_dev_data = [(month, authors_set, len(authors_set)) for month, authors_set in authors_by_month.items()]
                
                # Calculate throughput
                commits_and_authors = tc.extract_commits_and_authors(logs)
                throughput_data = [(month, authors_set, commit_count) for month, (authors_set, commit_count) in commits_and_authors.items()]
                
                # Calculate throughput per active developer (past 4 weeks) - weekly granularity
                normalized_throughput_data = tc.calculate_throughput_per_active_developer_by_week(logs, weeks_back=4)
                throughput_per_active_dev_data = [(week, commits, active_dev_count, throughput_per_dev) 
                                                 for week, (commits, active_dev_count, throughput_per_dev) in normalized_throughput_data.items()]
                
                # Calculate commit trends
                commits_by_author = ca.extract_commits_by_author(logs)
                commit_percentiles = ca.calculate_percentiles(commits_by_author)
                
                metrics = {
                    'repo_name': repo_name,
                    'cycle_time_data': cycle_time_data,
                    'failure_rate_data': failure_rate_data,
                    'active_dev_data': active_dev_data,
                    'throughput_data': throughput_data,
                    'throughput_per_active_dev_data': throughput_per_active_dev_data,
                    'commit_percentiles': commit_percentiles,
                    'total_commits': len(logs),
                    'total_authors': len(set(log._author[0] for log in logs)),
                    'date_range': self._get_date_range(logs)
                }
                
                # Cache the results
                self.metrics_cache[repo_name] = metrics
                
                logger.info(f"Successfully calculated metrics for repository '{repo_name}'")
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to calculate metrics for repository '{repo_name}': {e}")
            return {}
    
    def calculate_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate metrics for all repositories.
        
        Returns:
            Dict mapping repository names to their metrics
        """
        all_metrics = {}
        
        for repo_name in self.repo_manager.repositories.keys():
            metrics = self.calculate_repo_metrics(repo_name)
            if metrics:
                all_metrics[repo_name] = metrics
        
        return all_metrics
    
    def aggregate_cycle_time_metrics(self, metrics: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float, float, float, float]]:
        """
        Aggregate cycle time metrics across repositories.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of tuples (month, avg_sum, avg_average, avg_p75, avg_std)
        """
        monthly_data = defaultdict(list)
        
        for repo_name, repo_metrics in metrics.items():
            cycle_data = repo_metrics.get('cycle_time_data', [])
            for month, sum_val, avg_val, p75_val, std_val in cycle_data:
                monthly_data[month].append((sum_val, avg_val, p75_val, std_val))
        
        aggregated = []
        for month in sorted(monthly_data.keys()):
            data_points = monthly_data[month]
            if data_points:
                avg_sum = sum(point[0] for point in data_points) / len(data_points)
                avg_average = sum(point[1] for point in data_points) / len(data_points)
                avg_p75 = sum(point[2] for point in data_points) / len(data_points)
                avg_std = sum(point[3] for point in data_points) / len(data_points)
                
                aggregated.append((month, avg_sum, avg_average, avg_p75, avg_std))
        
        return aggregated
    
    def aggregate_failure_rate_metrics(self, metrics: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
        """
        Aggregate change failure rate metrics across repositories.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of tuples (month, avg_rate)
        """
        monthly_data = defaultdict(list)
        
        for repo_name, repo_metrics in metrics.items():
            failure_data = repo_metrics.get('failure_rate_data', [])
            for month, rate in failure_data:
                monthly_data[month].append(rate)
        
        aggregated = []
        for month in sorted(monthly_data.keys()):
            rates = monthly_data[month]
            if rates:
                avg_rate = sum(rates) / len(rates)
                aggregated.append((month, avg_rate))
        
        return aggregated
    
    def aggregate_active_developers_metrics(self, metrics: Dict[str, Dict[str, Any]]) -> List[Tuple[str, int]]:
        """
        Aggregate active developers metrics across repositories.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of tuples (month, total_unique_authors)
        """
        monthly_authors = defaultdict(set)
        
        for repo_name, repo_metrics in metrics.items():
            active_dev_data = repo_metrics.get('active_dev_data', [])
            for month, authors_set, commit_count in active_dev_data:
                monthly_authors[month].update(authors_set)
        
        aggregated = []
        for month in sorted(monthly_authors.keys()):
            total_authors = len(monthly_authors[month])
            aggregated.append((month, total_authors))
        
        return aggregated
    
    def aggregate_throughput_metrics(self, metrics: Dict[str, Dict[str, Any]]) -> List[Tuple[str, int]]:
        """
        Aggregate throughput metrics across repositories.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of tuples (month, total_commits)
        """
        monthly_commits = defaultdict(int)
        
        for repo_name, repo_metrics in metrics.items():
            throughput_data = repo_metrics.get('throughput_data', [])
            for month, authors_set, commit_count in throughput_data:
                monthly_commits[month] += commit_count
        
        aggregated = []
        for month in sorted(monthly_commits.keys()):
            total_commits = monthly_commits[month]
            aggregated.append((month, total_commits))
        
        return aggregated
    
    def aggregate_throughput_per_active_dev_metrics(self, metrics: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float]]:
        """
        Aggregate throughput per active developer metrics across repositories (weekly granularity).
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            List of tuples (week, average_throughput_per_active_dev)
        """
        weekly_data = defaultdict(lambda: {'total_commits': 0, 'total_active_devs': 0})
        
        for repo_name, repo_metrics in metrics.items():
            throughput_per_active_dev_data = repo_metrics.get('throughput_per_active_dev_data', [])
            for week, commits, active_dev_count, throughput_per_dev in throughput_per_active_dev_data:
                weekly_data[week]['total_commits'] += commits
                weekly_data[week]['total_active_devs'] += active_dev_count
        
        aggregated = []
        # Sort weeks chronologically by converting to datetime for proper sorting
        def week_sort_key(week_str):
            year, week_num = week_str.split('-W')
            return (int(year), int(week_num))
        
        for week in sorted(weekly_data.keys(), key=week_sort_key):
            data = weekly_data[week]
            if data['total_active_devs'] > 0:
                avg_throughput_per_active_dev = data['total_commits'] / data['total_active_devs']
            else:
                avg_throughput_per_active_dev = 0
            aggregated.append((week, avg_throughput_per_active_dev))
        
        return aggregated
    
    def generate_summary_report(self, metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary report across all repositories.
        
        Args:
            metrics: Dict of repository metrics
            
        Returns:
            Dict containing summary statistics
        """
        if not metrics:
            return {}
        
        summary = {
            'total_repositories': len(metrics),
            'total_commits': sum(repo_metrics.get('total_commits', 0) for repo_metrics in metrics.values()),
            'total_unique_authors': set(),
            'date_ranges': {},
            'repo_summaries': {}
        }
        
        for repo_name, repo_metrics in metrics.items():
            summary['total_unique_authors'].update(
                set(log._author[0] for log in git_log()) if 'logs' in locals() else set()
            )
            summary['date_ranges'][repo_name] = repo_metrics.get('date_range', {})
            
            # Individual repo summary
            summary['repo_summaries'][repo_name] = {
                'total_commits': repo_metrics.get('total_commits', 0),
                'total_authors': repo_metrics.get('total_authors', 0),
                'date_range': repo_metrics.get('date_range', {}),
                'avg_cycle_time': self._calculate_avg_cycle_time(repo_metrics.get('cycle_time_data', [])),
                'avg_failure_rate': self._calculate_avg_failure_rate(repo_metrics.get('failure_rate_data', []))
            }
        
        summary['total_unique_authors'] = len(summary['total_unique_authors'])
        
        return summary
    
    def save_aggregated_metrics(self, 
                              metrics: Dict[str, Dict[str, Any]], 
                              output_dir: str = "multi_repo_metrics") -> str:
        """
        Save aggregated metrics to files.
        
        Args:
            metrics: Dict of repository metrics
            output_dir: Directory to save metrics files
            
        Returns:
            Path to the output directory
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Save individual repository metrics
        for repo_name, repo_metrics in metrics.items():
            repo_file = os.path.join(output_dir, f"{repo_name}_metrics.json")
            with open(repo_file, 'w') as f:
                json.dump(repo_metrics, f, indent=2, default=str)
        
        # Save aggregated metrics
        aggregated_cycle_time = self.aggregate_cycle_time_metrics(metrics)
        aggregated_failure_rate = self.aggregate_failure_rate_metrics(metrics)
        aggregated_active_devs = self.aggregate_active_developers_metrics(metrics)
        aggregated_throughput = self.aggregate_throughput_metrics(metrics)
        aggregated_throughput_per_active_dev = self.aggregate_throughput_per_active_dev_metrics(metrics)
        
        # Save aggregated data as CSV
        if aggregated_cycle_time:
            df_cycle = pd.DataFrame(aggregated_cycle_time, 
                                  columns=['Month', 'Sum', 'Average', 'P75', 'Std'])
            df_cycle.to_csv(os.path.join(output_dir, 'aggregated_cycle_time.csv'), index=False)
        
        if aggregated_failure_rate:
            df_failure = pd.DataFrame(aggregated_failure_rate, 
                                    columns=['Month', 'Rate'])
            df_failure.to_csv(os.path.join(output_dir, 'aggregated_failure_rate.csv'), index=False)
        
        if aggregated_active_devs:
            df_devs = pd.DataFrame(aggregated_active_devs, 
                                 columns=['Month', 'ActiveDevelopers'])
            df_devs.to_csv(os.path.join(output_dir, 'aggregated_active_developers.csv'), index=False)
        
        if aggregated_throughput:
            df_throughput = pd.DataFrame(aggregated_throughput, 
                                       columns=['Month', 'Commits'])
            df_throughput.to_csv(os.path.join(output_dir, 'aggregated_throughput.csv'), index=False)
        
        if aggregated_throughput_per_active_dev:
            df_throughput_per_dev = pd.DataFrame(aggregated_throughput_per_active_dev, 
                                               columns=['Week', 'ThroughputPerActiveDev'])
            df_throughput_per_dev.to_csv(os.path.join(output_dir, 'aggregated_throughput_per_active_dev.csv'), index=False)
        
        # Save summary report
        summary = self.generate_summary_report(metrics)
        with open(os.path.join(output_dir, 'summary_report.json'), 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Saved aggregated metrics to {output_dir}")
        return output_dir
    
    def _get_date_range(self, logs: List) -> Dict[str, str]:
        """Get the date range of commits in logs."""
        if not logs:
            return {}
        
        timestamps = [log._when for log in logs]
        return {
            'start': datetime.fromtimestamp(min(timestamps)).isoformat(),
            'end': datetime.fromtimestamp(max(timestamps)).isoformat()
        }
    
    def _calculate_avg_cycle_time(self, cycle_data: List[Tuple]) -> float:
        """Calculate average cycle time from cycle data."""
        if not cycle_data:
            return 0.0
        
        p75_values = [point[3] for point in cycle_data]  # P75 values
        return sum(p75_values) / len(p75_values) if p75_values else 0.0
    
    def _calculate_avg_failure_rate(self, failure_data: List[Tuple]) -> float:
        """Calculate average failure rate from failure data."""
        if not failure_data:
            return 0.0
        
        rates = [point[1] for point in failure_data]
        return sum(rates) / len(rates) if rates else 0.0
