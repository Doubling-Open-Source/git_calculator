#!/usr/bin/env python3
"""
Multi-Repository Analysis Example

This example demonstrates how to use the git-calculator's multi-repository
functionality to analyze and compare DORA metrics across multiple repositories.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from multi_repo_manager import MultiRepoManager
from calculators.multi_repo_calculator import MultiRepoCalculator
from calculators.multi_repo_chart_generator import MultiRepoChartGenerator


def create_sample_repo_config():
    """Create a sample repository configuration."""
    config = {
        "repositories": [
            {
                "name": "frontend-app",
                "path_or_url": "/path/to/local/frontend",
                "branch": "main",
                "description": "Frontend application repository"
            },
            {
                "name": "backend-api", 
                "path_or_url": "https://github.com/example/backend-api.git",
                "branch": "develop",
                "description": "Backend API repository"
            },
            {
                "name": "mobile-app",
                "path_or_url": "git@github.com:example/mobile-app.git",
                "description": "Mobile application repository"
            }
        ]
    }
    
    config_file = "sample_repo_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created sample configuration: {config_file}")
    return config_file


def analyze_multiple_repositories_example():
    """Example of analyzing multiple repositories."""
    print("=== Multi-Repository Analysis Example ===\n")
    
    # Create sample configuration
    config_file = create_sample_repo_config()
    
    # Load repository configuration
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    repositories = config['repositories']
    print(f"Analyzing {len(repositories)} repositories:")
    for repo in repositories:
        print(f"  - {repo['name']}: {repo['path_or_url']}")
    print()
    
    # Initialize repository manager
    with MultiRepoManager() as repo_manager:
        print("Adding repositories to manager...")
        
        # Add repositories
        for repo_config in repositories:
            success = repo_manager.add_repository(
                name=repo_config['name'],
                path_or_url=repo_config['path_or_url'],
                branch=repo_config.get('branch'),
                description=repo_config.get('description')
            )
            print(f"  {'✓' if success else '✗'} {repo_config['name']}")
        
        print("\nCloning remote repositories...")
        clone_results = repo_manager.clone_repositories()
        for repo_name, success in clone_results.items():
            print(f"  {'✓' if success else '✗'} {repo_name}")
        
        # Check if we have any successful repositories
        successful_repos = [name for name, success in clone_results.items() if success]
        if not successful_repos:
            print("\nNo repositories were successfully processed. This example requires:")
            print("1. Valid local repository paths, or")
            print("2. Access to the example GitHub repositories")
            print("\nPlease update the configuration with your own repositories.")
            return
        
        print(f"\nCalculating metrics for {len(successful_repos)} repositories...")
        
        # Calculate metrics
        calculator = MultiRepoCalculator(repo_manager)
        all_metrics = calculator.calculate_all_metrics()
        
        if not all_metrics:
            print("No metrics were calculated. This might be due to:")
            print("- Repository access issues")
            print("- Empty repositories")
            print("- Git command failures")
            return
        
        print(f"Successfully calculated metrics for {len(all_metrics)} repositories:")
        for repo_name, metrics in all_metrics.items():
            total_commits = metrics.get('total_commits', 0)
            total_authors = metrics.get('total_authors', 0)
            print(f"  - {repo_name}: {total_commits} commits, {total_authors} authors")
        
        # Save aggregated metrics
        print("\nSaving aggregated metrics...")
        metrics_dir = calculator.save_aggregated_metrics(all_metrics, "example_multi_repo_metrics")
        print(f"Metrics saved to: {metrics_dir}")
        
        # Generate comparison charts
        print("\nGenerating comparison charts...")
        chart_generator = MultiRepoChartGenerator("example_multi_repo_charts")
        generated_charts = chart_generator.generate_all_comparison_charts(all_metrics)
        
        print(f"Generated {len(generated_charts)} charts:")
        for chart_path in generated_charts:
            print(f"  - {chart_path}")
        
        # Generate summary report
        summary = calculator.generate_summary_report(all_metrics)
        summary_file = "example_summary_report.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\nSummary report saved to: {summary_file}")
        print("\n=== Analysis Complete ===")
        print(f"Results available in:")
        print(f"  - Metrics: {metrics_dir}")
        print(f"  - Charts: example_multi_repo_charts/")
        print(f"  - Summary: {summary_file}")


def programmatic_example():
    """Example of programmatic multi-repository analysis."""
    print("\n=== Programmatic Analysis Example ===\n")
    
    # This example shows how to use the multi-repo functionality programmatically
    # Note: This requires actual repository paths/URLs
    
    example_repos = [
        {
            "name": "repo1",
            "path_or_url": "/path/to/your/repo1",  # Replace with actual path
            "description": "First repository"
        },
        {
            "name": "repo2", 
            "path_or_url": "/path/to/your/repo2",  # Replace with actual path
            "description": "Second repository"
        }
    ]
    
    print("Example programmatic usage:")
    print("""
    from src.multi_repo_manager import MultiRepoManager
    from src.calculators.multi_repo_calculator import MultiRepoCalculator
    from src.calculators.multi_repo_chart_generator import MultiRepoChartGenerator
    
    # Initialize repository manager
    with MultiRepoManager() as repo_manager:
        # Add repositories
        for repo in repositories:
            repo_manager.add_repository(
                name=repo['name'],
                path_or_url=repo['path_or_url'],
                description=repo.get('description')
            )
        
        # Clone and calculate metrics
        repo_manager.clone_repositories()
        calculator = MultiRepoCalculator(repo_manager)
        all_metrics = calculator.calculate_all_metrics()
        
        # Generate charts
        chart_generator = MultiRepoChartGenerator("charts")
        chart_generator.generate_all_comparison_charts(all_metrics)
    """)


if __name__ == '__main__':
    print("Git Calculator - Multi-Repository Analysis Example")
    print("=" * 50)
    
    # Run the example
    try:
        analyze_multiple_repositories_example()
        programmatic_example()
        
    except KeyboardInterrupt:
        print("\n\nExample interrupted by user.")
    except Exception as e:
        print(f"\n\nExample failed with error: {e}")
        print("This is expected if you don't have access to the example repositories.")
        print("Please update the configuration with your own repository paths/URLs.")
    
    print("\nTo use this example with your own repositories:")
    print("1. Update the repository paths/URLs in the configuration")
    print("2. Ensure you have access to the repositories")
    print("3. Run the example again")
