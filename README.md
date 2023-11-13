# git-calculator
Calculate dora metrics and related from a Git repository on the local file system. Does not require integration with GitHub or any other git service provider.

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