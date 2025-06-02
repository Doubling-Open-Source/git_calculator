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

# Get the data
logs = gir.git_log()

# Calculate cycle time
tds = commit_calc.calculate_time_deltas(logs)
cycle_time_data = commit_calc.commit_statistics_normalized_by_month(tds)

# Calculate change failure rate
data_by_month = cfc.extract_commit_data(logs)
failure_rate_data = [(month, rate) for month, rate in cfc.calculate_change_failure_rate(data_by_month).items()]

# Generate charts and save data
cg.generate_charts(cycle_time_data=cycle_time_data, 
                  failure_rate_data=failure_rate_data,
                  save_data=True)
```

4. Check your results:
   - A new `metrics` directory will be created in your repository
   - You'll find four files with your repository name as prefix:
     - `metrics/{repo_name}_cycle_time_data.csv` - Raw cycle time data
     - `metrics/{repo_name}_change_failure_data.csv` - Raw change failure rate data
     - `metrics/{repo_name}_cycle_time_chart.png` - Cycle time chart
     - `metrics/{repo_name}_change_failure_rate_chart.png` - Change failure rate chart

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
│   │   └── cycle_time_calculator_by_commits.py  # Cycle time stats by commit
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

```
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

# Generating Charts

To generate modern-looking charts with trendlines for both metrics:

```py
# Launch python3 
python
# Paste:
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

# Generate charts
cg.generate_charts(cycle_time_data=cycle_time_data, failure_rate_data=failure_rate_data)
```

This will create two files:
1. `cycle_time_chart.png` - Shows the average cycle time trend with:
   - A line showing the average cycle time
   - A trendline showing the overall direction
   - A shaded area showing the standard deviation
   - Clear labels and a modern style

2. `change_failure_rate_chart.png` - Shows the change failure rate trend with:
   - A line showing the failure rate
   - A trendline showing the overall direction
   - A reference line at 15% (industry standard)
   - Clear labels and a modern style

You can also generate just one chart at a time:
```py
# Just cycle time
cg.plot_cycle_time(cycle_time_data)

# Just change failure rate
cg.plot_change_failure_rate(failure_rate_data)
```

The charts will be saved as high-resolution PNG files (300 DPI) in your current directory.

# Saving and Loading Metrics Data

You can save the calculated metrics data to CSV files and generate charts from them later:

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
