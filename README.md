# git-calculator
Calculate dora metrics and related from a Git repository on the local file system. Does not require integration with GitHub or any other git service provider.

# Getting Started

1. First, clone this repository and set it up:
```sh
# Clone the repository
git clone https://github.com/yourusername/git-calculator.git
cd git-calculator

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
pip install -r requirements.txt

# Set Python path
export PYTHONPATH=$(pwd)  # On Windows, use: set PYTHONPATH=%cd%
```

2. Navigate to the Git repository you want to analyze:
```sh
cd /path/to/your/repository
```

3. Run Python and calculate your metrics:
```py
# Launch Python
python

# Import required modules
from src import git_ir as gir
from src.calculators import cycle_time_by_commits_calculator as commit_calc
from src.calculators import change_failure_calculator as cfc
from src.calculators import chart_generator as cg
from src.calculators import commit_analyzer as ca

# Get the data
logs = gir.git_log()

# Calculate cycle time
tds = commit_calc.calculate_time_deltas(logs)
cycle_time_data = commit_calc.commit_statistics_normalized_by_month(tds)

# Calculate change failure rate
data_by_month = cfc.extract_commit_data(logs)
failure_rate_data = [(month, rate) for month, rate in cfc.calculate_change_failure_rate(data_by_month).items()]

# Analyze commit trends by author
ca.analyze_commits()

# Generate charts and save data
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data,
                  save_data=True)
```

4. Check your results:
   - A new `metrics` directory will be created in your repository
   - You'll find several files with your repository name as prefix:
     - `metrics/{repo_name}_cycle_time_data.csv` - Raw cycle time data
     - `metrics/{repo_name}_change_failure_data.csv` - Raw change failure rate data
     - `metrics/{repo_name}_cycle_time_chart.png` - Cycle time chart
     - `metrics/{repo_name}_change_failure_rate_chart.png` - Change failure rate chart
     - `metrics/commit_trends.png` - Commit trends by author
     - `metrics/commit_{author}_commits.csv` - Individual author commit data
     - `metrics/commit_percentiles.csv` - Author commit percentiles

5. To generate new charts later without recalculating:
```py
from src.calculators import chart_generator as cg

# Load the saved data
cycle_time_data, failure_rate_data = cg.load_metrics_data()

# Generate new charts
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data)
```

# Project Outline

```
git-calculator/
│
├── src/
|   ├── git_ir.py        # In memory representation of Git metadata
│   ├── calculators/
│   │   ├── cycle_time_calculator_by_branches.py  # Cycle time stats by branch
│   │   ├── cycle_time_calculator_by_commits.py  # Cycle time stats by commit
│   │   ├── change_failure_calculator.py         # Change failure rate stats
│   │   ├── commit_analyzer.py                   # Commit trends by author
│   │   └── chart_generator.py                   # Chart generation utilities
│   ├── util/
│   │   ├── git_util.py  # Helpers for interacting with a Git repo
│   │   └── toy_repo.py  # Temporary toy repo on the filesystem for testing
│
├── tests/
│   └── test_*.py        # Unit tests
│
├── README.md             # Documentation
├── requirements.txt      # Dependencies
└── setup.py              # Setup
```

# Project Setup

```
cd git-calculator
export PYTHONPATH=$(pwd)
```

Set up virtual environment:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Project Testing

Run unit tests
```
pytest -v
```

For debugging:
```export PYTEST_ADDOPTS="--log-cli-level=DEBUG"```

# Project Playing Around

To play around with the interpreter:
```
python
from src.util.toy_repo import ToyRepoCreator
trc = ToyRepoCreator("/Users/denalilumma/doubling-code/scratch")
even_intervals = [7 * i for i in range(12)]  # Weekly intervals
trc.create_custom_commits(even_intervals)
```
(Replace with your local path)

```
from src.calculators.cycle_time_by_commits_calculator import cycle_time_between_commits_by_author
result = cycle_time_between_commits_by_author(None, bucket_size=4, window_size=2)
print(result)
```

# Project Usage

To calculate statistics for a given repository, proceed with the following sequence.


Step one, go to this repo in the terminal and set the python path:

```sh
cd git_calculator
export PYTHONPATH=$(pwd)
```

Set up virtual environment:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Finally, go to the git repo you want to analyze:
```sh
cd tensorflow
```

Analyze:
```py
# Launch python3 
python
# Paste:
from src import git_ir as gir
from src.calculators import cycle_time_by_commits_calculator as commit_calc
logs = gir.git_log()
tds = commit_calc.calculate_time_deltas(logs)
result = commit_calc.commit_statistics_normalized_by_month(tds)
commit_calc.write_commit_statistics_to_file(result, "scratch.csv") # Default file name is "a.csv"
```

Example output:
```csv
INTERVAL START, SUM, AVERAGE, p75 CYCLE TIME (minutes), std CYCLE TIME
2023-10,161280.0,40320.0,40320,0
2023-11,120960.0,40320.0,40320,0
```

To calculate change failure rate:
```py
# Launch python3 
python
# Paste:
from src import git_ir as gir
from src.calculators import change_failure_calculator as cfc
logs = gir.git_log()
data_by_month = cfc.extract_commit_data(logs)
change_failure_rates = cfc.calculate_change_failure_rate(data_by_month)
cfc.write_change_failure_rate_to_file(change_failure_rates, "change_failure_rate.csv") # Default file name is "change_failure_rate_by_month.csv"
```

Example output:
```csv
Month,Change Failure Rate (%)
2023-10,25.0
2023-11,33.3
```

The change failure rate is calculated by identifying commits that contain keywords like "revert", "hotfix", "bugfix", "bug", "fix", "problem", or "issue" in their commit messages. The rate is expressed as a percentage of total commits that required fixes.

To analyze commit trends by author:
```py
# Launch python3 
python
# Paste:
from src.calculators import commit_analyzer as ca
ca.analyze_commits()
```

This will generate:
- A commit trends chart showing commits over time for each author
- CSV files with individual author commit data
- A CSV file with commit percentiles for all authors

# Generating Charts

To generate modern-looking charts with trendlines for both metrics:

```py
# First time: Calculate and save the data
from src import git_ir as gir
from src.calculators import cycle_time_by_commits_calculator as commit_calc
from src.calculators import change_failure_calculator as cfc
from src.calculators import chart_generator as cg

# Get the data
logs = gir.git_log()

# Calculate cycle time
tds = commit_calc.calculate_time_deltas(logs)
cycle_time_data = commit_calc.commit_statistics_normalized_by_month(tds)

# Calculate change failure rate
data_by_month = cfc.extract_commit_data(logs)
failure_rate_data = [(month, rate) for month, rate in cfc.calculate_change_failure_rate(data_by_month).items()]

# Save data and generate charts
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data,
                  save_data=True)

# Later: Load saved data and generate new charts
from src.calculators import chart_generator as cg

# Load the saved data
cycle_time_data, failure_rate_data = cg.load_metrics_data()

# Generate new charts
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data)
```

This will create a `metrics` directory in your repository and save four files with the repository name as prefix (e.g., `tensorflow_cycle_time_data.csv`):
1. `metrics/{repo_name}_cycle_time_data.csv` - Raw cycle time data
2. `metrics/{repo_name}_change_failure_data.csv` - Raw change failure rate data
3. `metrics/{repo_name}_cycle_time_chart.png` - Cycle time chart
4. `metrics/{repo_name}_change_failure_rate_chart.png` - Change failure rate chart

The repository name is automatically detected from:
1. The git remote URL (e.g., `git@github.com:user/tensorflow.git` → `tensorflow`)
2. If no remote is found, the current directory name is used
3. If neither is available, `repo` is used as a fallback

You can also use a custom prefix instead of the repository name:
```py
# Save with custom prefix
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data,
                  save_data=True,
                  prefix='team_a_')

# Load with custom prefix
cycle_time_data, failure_rate_data = cg.load_metrics_data(prefix='team_a_')
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data)
```

This is useful when you want to compare metrics across different teams or time periods.

# Multi-Repository Analysis

The git-calculator now supports analyzing multiple repositories simultaneously, allowing you to compare DORA metrics across different projects, teams, or time periods.

## Command Line Interface

The easiest way to use multi-repository analysis is through the command-line interface:

### Single Repository Analysis

```bash
# Analyze a single repository
python -m src.cli single /path/to/repo

# Specify custom output directory
python -m src.cli single /path/to/repo --output my_analysis
```

### Multiple Repository Analysis

1. **Create a repository configuration file:**

```bash
# Create a sample configuration file
python -m src.cli config --create-sample
```

This creates a `repo_config.json` file with the following structure:

```json
{
  "repositories": [
    {
      "name": "frontend-app",
      "path_or_url": "/path/to/local/frontend",
      "branch": "main",
      "description": "Frontend application repository"
    },
    {
      "name": "backend-api", 
      "path_or_url": "https://github.com/company/backend-api.git",
      "branch": "develop",
      "description": "Backend API repository"
    },
    {
      "name": "mobile-app",
      "path_or_url": "git@github.com:company/mobile-app.git",
      "description": "Mobile application repository"
    }
  ]
}
```

2. **Analyze multiple repositories:**

```bash
# Analyze repositories from config file
python -m src.cli multi --config repo_config.json

# Update repositories before analysis
python -m src.cli multi --config repo_config.json --update

# Specify custom output directory
python -m src.cli multi --config repo_config.json --output team_analysis
```

### Configuration Options

The repository configuration supports:

- **Local paths**: `/path/to/local/repo`
- **HTTPS URLs**: `https://github.com/user/repo.git`
- **SSH URLs**: `git@github.com:user/repo.git`
- **Specific branches**: `"branch": "develop"`
- **Descriptions**: `"description": "Project description"`

## Programmatic Multi-Repository Analysis

You can also use the multi-repository functionality programmatically:

```python
from src.multi_repo_manager import MultiRepoManager
from src.calculators.multi_repo_calculator import MultiRepoCalculator
from src.calculators.multi_repo_chart_generator import MultiRepoChartGenerator

# Initialize repository manager
with MultiRepoManager() as repo_manager:
    # Add repositories
    repo_manager.add_repository("frontend", "/path/to/frontend")
    repo_manager.add_repository("backend", "https://github.com/user/backend.git")
    repo_manager.add_repository("mobile", "git@github.com:user/mobile.git")
    
    # Clone remote repositories
    clone_results = repo_manager.clone_repositories()
    print(f"Clone results: {clone_results}")
    
    # Calculate metrics for all repositories
    calculator = MultiRepoCalculator(repo_manager)
    all_metrics = calculator.calculate_all_metrics()
    
    # Save aggregated metrics
    calculator.save_aggregated_metrics(all_metrics, "multi_repo_metrics")
    
    # Generate comparison charts
    chart_generator = MultiRepoChartGenerator("multi_repo_charts")
    generated_charts = chart_generator.generate_all_comparison_charts(all_metrics)
    
    print(f"Generated {len(generated_charts)} comparison charts")
```

## Multi-Repository Output

When analyzing multiple repositories, the tool creates:

### Directory Structure
```
multi_repo_analysis/
├── metrics/
│   ├── frontend_metrics.json
│   ├── backend_metrics.json
│   ├── mobile_metrics.json
│   ├── aggregated_cycle_time.csv
│   ├── aggregated_failure_rate.csv
│   ├── aggregated_active_developers.csv
│   ├── aggregated_throughput.csv
│   └── summary_report.json
└── charts/
    ├── cycle_time_comparison.png
    ├── failure_rate_comparison.png
    ├── active_developers_comparison.png
    ├── throughput_comparison.png
    └── repository_summary.png
```

### Individual Repository Metrics
Each repository gets its own JSON file with detailed metrics:
- Cycle time data (monthly)
- Change failure rate data (monthly)
- Active developers data (monthly)
- Throughput data (monthly)
- Commit percentiles
- Total commits and authors
- Date range of analysis

### Aggregated Metrics
- **aggregated_cycle_time.csv**: Average cycle time across all repositories
- **aggregated_failure_rate.csv**: Average change failure rate across all repositories
- **aggregated_active_developers.csv**: Total unique active developers across all repositories
- **aggregated_throughput.csv**: Total commits across all repositories

### Comparison Charts
- **cycle_time_comparison.png**: Line chart comparing cycle time trends across repositories
- **failure_rate_comparison.png**: Line chart comparing change failure rates across repositories
- **active_developers_comparison.png**: Line chart comparing active developer counts across repositories
- **throughput_comparison.png**: Line chart comparing commit throughput across repositories
- **repository_summary.png**: Bar charts showing key metrics comparison across repositories

### Summary Report
The `summary_report.json` contains:
- Total number of repositories analyzed
- Total commits across all repositories
- Total unique authors across all repositories
- Date ranges for each repository
- Individual repository summaries with key metrics

## Advanced Usage

### Custom Workspace Directory

```python
# Use a custom workspace for cloned repositories
with MultiRepoManager(workspace_dir="/tmp/my_analysis") as repo_manager:
    # ... analysis code ...
```

### Repository Context Management

```python
# Temporarily work with a specific repository
with repo_manager.repository_context("frontend"):
    logs = git_log()
    # ... perform analysis ...
```

### Selective Analysis

```python
# Calculate metrics for specific repositories only
calculator = MultiRepoCalculator(repo_manager)
frontend_metrics = calculator.calculate_repo_metrics("frontend")
backend_metrics = calculator.calculate_repo_metrics("backend")

# Generate charts for specific repositories
selected_metrics = {
    "frontend": frontend_metrics,
    "backend": backend_metrics
}
chart_generator.generate_all_comparison_charts(selected_metrics)
```

## Use Cases

Multi-repository analysis is particularly useful for:

1. **Team Comparison**: Compare DORA metrics across different development teams
2. **Project Comparison**: Analyze performance across different projects or products
3. **Technology Stack Analysis**: Compare metrics between different technology stacks
4. **Time Period Analysis**: Compare metrics across different time periods
5. **Merger/Acquisition Analysis**: Analyze metrics before and after organizational changes
6. **Benchmarking**: Establish baseline metrics across multiple repositories

## Performance Considerations

- **Large Repositories**: Analysis time scales with repository size and commit history
- **Network Operations**: Cloning remote repositories requires network access
- **Memory Usage**: Multiple repositories may require significant memory for analysis
- **Caching**: Metrics are cached to avoid recalculation during the same session

## Troubleshooting

### Common Issues

1. **Repository Access**: Ensure you have access to all repositories (SSH keys, authentication)
2. **Branch Availability**: Verify that specified branches exist in remote repositories
3. **Disk Space**: Ensure sufficient disk space for cloning repositories
4. **Permissions**: Check file system permissions for output directories

### Debug Mode

```bash
# Enable verbose logging
python -m src.cli multi --config repo_config.json --verbose
```

### Error Handling

The tool provides detailed error messages and continues processing other repositories even if some fail. Check the logs for specific error details.
