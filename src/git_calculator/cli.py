#!/usr/bin/env python3
"""
Command Line Interface for Git Calculator

This module provides a CLI for analyzing single or multiple Git repositories.
"""

import argparse
import json
import logging
import os
import sys
from typing import List

from git_calculator.multi_repo_manager import MultiRepoManager
from git_calculator.calculators.multi_repo_calculator import MultiRepoCalculator
from git_calculator.visualizers.multi_repo_chart_generator import MultiRepoChartGenerator
from git_calculator.visualizers.chart_generator import (
    generate_charts,
    generate_charts_sql,
    get_repo_name,
)
from git_calculator import git_ir as gir
from git_calculator.analyze_window import (
    analyze_window,
    parse_utc_instant,
    window_series_csv_path,
    write_window_series_csv,
)
from git_calculator.calculators import (
    cycle_time_by_commits_calculator as cycle_calc,
    change_failure_calculator as cfc,
    commit_analyzer as ca,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def analyze_single_repo(
    repo_path: str,
    output_dir: str = "metrics",
    backend: str = "python",
    work_style: str = "all-branches",
    default_branch: str | None = None,
) -> bool:
    """
    Analyze a single repository.

    Args:
        repo_path: Path to the repository
        output_dir: Directory to save outputs
        backend: 'python' (default) or 'sql' for cycle-time calculation

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Change to repository directory
        original_cwd = os.getcwd()
        os.chdir(repo_path)

        # Get the data
        logger.info(f"Analyzing repository at: {repo_path} (backend={backend})")

        logs = gir.git_log(work_style=work_style, default_branch=default_branch)
        if backend == "sql":
            # Analyze commit trends by author
            ca.analyze_commits()

            # Generate charts and save data
            # Backend-specific prefix so Python and SQL outputs can coexist for comparison
            chart_prefix = f"{get_repo_name()}_sql_"
            generate_charts_sql(
                logs=logs,
                save_data=True,
                prefix=chart_prefix,
                work_style=work_style,
            )
        else:
            # Calculate cycle time
            tds = cycle_calc.calculate_time_deltas(logs)
            cycle_time_data = cycle_calc.commit_statistics_normalized_by_month(tds)
            # Calculate change failure rate
            data_by_month = cfc.extract_commit_data(logs, work_style=work_style)
            failure_rate_data = [
                (month, rate)
                for month, rate in cfc.calculate_change_failure_rate(
                    data_by_month
                ).items()
            ]

            # Analyze commit trends by author
            ca.analyze_commits()

            # Generate charts and save data
            generate_charts(
                cycle_time_data=cycle_time_data,
                failure_rate_data=failure_rate_data,
                save_data=True,
            )

        logger.info(f"Successfully analyzed repository. Results saved to {output_dir}")
        return True

    except Exception as e:
        logger.error(f"Failed to analyze repository: {e}")
        return False
    finally:
        os.chdir(original_cwd)


def analyze_multiple_repos(
    repo_configs: List[dict],
    output_dir: str = "multi_repo_analysis",
    update_repos: bool = False,
) -> bool:
    """
    Analyze multiple repositories.

    Args:
        repo_configs: List of repository configurations
        output_dir: Directory to save outputs
        update_repos: Whether to update repositories before analysis

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(
            f"Starting multi-repository analysis with {len(repo_configs)} repositories"
        )

        # Initialize repository manager
        with MultiRepoManager() as repo_manager:
            # Add repositories
            for config in repo_configs:
                success = repo_manager.add_repository(
                    name=config["name"],
                    path_or_url=config["path_or_url"],
                    branch=config.get("branch"),
                    description=config.get("description"),
                )
                if not success:
                    logger.error(f"Failed to add repository: {config['name']}")
                    return False

            # Clone repositories if needed
            clone_results = repo_manager.clone_repositories()
            failed_repos = [
                name for name, success in clone_results.items() if not success
            ]
            if failed_repos:
                logger.error(f"Failed to clone repositories: {failed_repos}")
                return False

            # Update repositories if requested
            if update_repos:
                update_results = repo_manager.update_repositories()
                failed_updates = [
                    name for name, success in update_results.items() if not success
                ]
                if failed_updates:
                    logger.warning(f"Failed to update repositories: {failed_updates}")

            # Calculate metrics
            calculator = MultiRepoCalculator(repo_manager)
            all_metrics = calculator.calculate_all_metrics()

            if not all_metrics:
                logger.error("No metrics calculated for any repository")
                return False

            # Save aggregated metrics
            metrics_dir = os.path.join(output_dir, "metrics")
            calculator.save_aggregated_metrics(all_metrics, metrics_dir)

            # Generate comparison charts
            chart_generator = MultiRepoChartGenerator(
                os.path.join(output_dir, "charts")
            )
            generated_charts = chart_generator.generate_all_comparison_charts(
                all_metrics
            )

            # Generate summary report
            summary = calculator.generate_summary_report(all_metrics)
            summary_file = os.path.join(output_dir, "summary_report.json")
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2, default=str)

            logger.info("Multi-repository analysis completed successfully!")
            logger.info(f"Results saved to: {output_dir}")
            logger.info(f"Generated {len(generated_charts)} comparison charts")

            return True

    except Exception as e:
        logger.error(f"Failed to analyze multiple repositories: {e}")
        return False


def load_repo_config(config_file: str) -> List[dict]:
    """
    Load repository configuration from a JSON file.

    Args:
        config_file: Path to the configuration file

    Returns:
        List of repository configurations
    """
    try:
        with open(config_file, "r") as f:
            config = json.load(f)

        if "repositories" not in config:
            raise ValueError("Configuration file must contain 'repositories' key")

        return config["repositories"]

    except Exception as e:
        logger.error(f"Failed to load configuration file: {e}")
        return []


def create_sample_config(output_file: str = "repo_config.json") -> str:
    """
    Create a sample repository configuration file.

    Args:
        output_file: Path to save the sample configuration

    Returns:
        Path to the created configuration file
    """
    sample_config = {
        "repositories": [
            {
                "name": "repo1",
                "path_or_url": "/path/to/local/repo1",
                "branch": "main",
                "description": "First repository for analysis",
            },
            {
                "name": "repo2",
                "path_or_url": "https://github.com/user/repo2.git",
                "branch": "develop",
                "description": "Second repository from GitHub",
            },
            {
                "name": "repo3",
                "path_or_url": "git@github.com:user/repo3.git",
                "description": "Third repository via SSH",
            },
        ]
    }

    with open(output_file, "w") as f:
        json.dump(sample_config, f, indent=2)

    logger.info(f"Sample configuration created: {output_file}")
    return output_file


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Git Calculator - Analyze DORA metrics from Git repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a single repository
  git-calculator single /path/to/repo

  # Single repo with SQL backend (compare charts: <repo>_cycle_time_chart.png vs <repo>_sql_cycle_time_chart.png)
  git-calculator single /path/to/repo --output my_analysis --backend sql

  # Windowed SQL series at weekly grain
  git-calculator single /path/to/repo --from 2026-06-22T00:00:00Z --to 2026-08-17T00:00:00Z --grain weekly --backend sql

  # Analyze multiple repositories from config file
  git-calculator multi --config repo_config.json

  # Create a sample configuration file
  git-calculator config --create-sample

  # Analyze multiple repositories with updates
  git-calculator multi --config repo_config.json --update
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Single repository analysis
    single_parser = subparsers.add_parser("single", help="Analyze a single repository")
    single_parser.add_argument("repo_path", help="Path to the repository")
    single_parser.add_argument(
        "--output", "-o", default="metrics", help="Output directory (default: metrics)"
    )
    single_parser.add_argument(
        "--backend",
        "-b",
        choices=["python", "sql"],
        default="python",
        help="Cycle-time backend: python (default) or sql; use sql to compare visual results",
    )
    single_parser.add_argument(
        "--work-style",
        choices=["all-branches", "squash"],
        default="all-branches",
        help="all-branches: every ref (default). squash: default branch only; change-failure uses the summary",
    )
    single_parser.add_argument(
        "--from",
        dest="window_from",
        default=None,
        help="UTC window start (RFC3339). Requires --to. Half-open [from, to).",
    )
    single_parser.add_argument(
        "--to",
        dest="window_to",
        default=None,
        help="UTC window end (RFC3339). Requires --from. Half-open [from, to).",
    )
    single_parser.add_argument(
        "--grain",
        choices=["weekly", "monthly"],
        default="monthly",
        help="Row aggregation for a windowed SQL run (default: monthly)",
    )
    single_parser.add_argument(
        "--default-branch",
        default=None,
        help="Override default-branch detection for --work-style squash",
    )

    # Multiple repository analysis
    multi_parser = subparsers.add_parser("multi", help="Analyze multiple repositories")
    multi_parser.add_argument(
        "--config", "-c", required=True, help="Configuration file with repository list"
    )
    multi_parser.add_argument(
        "--output",
        "-o",
        default="multi_repo_analysis",
        help="Output directory (default: multi_repo_analysis)",
    )
    multi_parser.add_argument(
        "--update", action="store_true", help="Update repositories before analysis"
    )

    # Configuration management
    config_parser = subparsers.add_parser(
        "config", help="Manage repository configurations"
    )
    config_parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create a sample configuration file",
    )
    config_parser.add_argument(
        "--output",
        "-o",
        default="repo_config.json",
        help="Output file for sample configuration",
    )

    # Global options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress output except errors"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    # Execute commands
    if args.command == "single":
        has_from = args.window_from is not None
        has_to = args.window_to is not None
        if has_from ^ has_to:
            single_parser.error("--from and --to must be provided together")
        if args.grain == "weekly" and not has_from:
            single_parser.error("--grain weekly requires --from and --to")
        if has_from and args.backend != "sql":
            single_parser.error("a window requires --backend sql")
        if has_from:
            try:
                window_start = parse_utc_instant(args.window_from, label="--from")
                window_end = parse_utc_instant(args.window_to, label="--to")
                series = analyze_window(
                    args.repo_path,
                    window_start=window_start,
                    window_end=window_end,
                    grain=args.grain,
                    backend=args.backend,
                    work_style=args.work_style,
                    default_branch=args.default_branch,
                )
                csv_path = window_series_csv_path(args.repo_path, args.output)
                write_window_series_csv(series, csv_path)
            except (ValueError, RuntimeError) as exc:
                logger.error("Failed to analyze repository: %s", exc)
                sys.exit(1)
            sys.exit(0)
        success = analyze_single_repo(
            args.repo_path,
            args.output,
            args.backend,
            args.work_style,
            default_branch=args.default_branch,
        )
        sys.exit(0 if success else 1)

    elif args.command == "multi":
        repo_configs = load_repo_config(args.config)
        if not repo_configs:
            logger.error("No valid repository configurations found")
            sys.exit(1)

        success = analyze_multiple_repos(repo_configs, args.output, args.update)
        sys.exit(0 if success else 1)

    elif args.command == "config":
        if args.create_sample:
            create_sample_config(args.output)
        else:
            config_parser.print_help()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
