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

Step three, analyze:
```py
# Launch python3 
python
# Paste:
from src import git_ir as gir
from src.calculators import cycle_time_by_commits_calculator as commit_calc
logs = gir.git_log()
tds = commit_calc.calculate_time_deltas(logs)
result = commit_calc.commit_statistics_normalized_by_month(tds)
```

You can now open `a.svg` in your browser.

Example output:
```csv
INTERVAL START, BRANCHES, COMMITS, p50 COMMITS, p50 CYCLETIME, p50 QA, p50 WORKTIME, p75 COMMITS, p75 CYCLETIME, p75 QA, p75 WORKTIME, avg COMMITS, avg CYCLETIME, avg QA, avg WORKTIME, std COMMITS, std CYCLETIME, std QA, std WORKTIME,
Tue Mar 15 07:22:42 2022,48,141,1.5,1.45,0.02,0.0,3.25,3.22,0.21,1.78,2.94,3.08,0.46,1.75,3.4,3.95,1.37,3.59
Thu Aug  4 14:05:53 2022,48,105,1.5,0.72,0.01,0.0,3.0,0.98,0.06,0.04,2.19,0.88,0.14,0.31,1.61,1.23,0.33,1.17
Tue Sep 13 08:38:27 2022,48,118,1.0,0.43,0.01,0.0,2.25,0.99,0.1,0.04,2.46,0.83,0.22,0.3,3.26,1.23,0.45,1.09
Mon Oct  3 07:56:39 2022,48,143,2.0,0.62,0.03,0.0,3.0,0.96,0.17,0.09,2.98,0.67,0.22,0.13,3.35,0.62,0.46,0.27
Fri Oct 21 06:32:55 2022,48,94,1.0,0.54,0.03,0.0,2.0,0.96,0.07,0.06,1.96,0.81,0.15,0.3,1.79,1.16,0.41,1.03
Wed Nov  9 12:24:56 2022,48,137,1.0,0.24,0.01,0.0,2.0,1.1,0.06,0.03,2.85,1.51,0.42,0.73,4.25,4.38,1.88,3.9
Thu Dec  8 05:59:28 2022,48,97,1.0,0.91,0.05,0.0,2.25,2.07,0.35,0.9,2.02,2.29,1.17,0.64,1.67,5.52,5.37,1.35
Tue Jan 17 14:02:31 2023,48,187,1.0,0.21,0.01,0.0,3.25,0.98,0.08,0.08,3.9,1.88,0.2,1.41,6.64,5.57,0.5,5.28
Fri Feb  3 09:23:24 2023,48,147,1.0,1.06,0.01,0.01,3.25,3.03,0.11,1.09,3.06,1.92,0.27,1.09,3.56,2.37,1.0,1.98
Fri Mar  3 15:29:06 2023,48,85,1.0,0.46,0.04,0.0,2.0,1.73,0.61,0.01,1.77,1.33,0.79,0.26,1.51,2.55,2.48,0.75
Tue Mar 14 10:55:46 2023,48,147,1.0,0.74,0.04,0.0,3.0,1.74,0.13,0.91,3.06,1.22,0.31,0.42,4.61,1.43,0.68,0.78
Thu Apr 20 15:50:07 2023,48,107,1.0,1.13,0.09,0.0,2.0,1.71,0.45,0.56,2.23,3.83,2.54,0.78,2.61,11.48,11.27,2.11
Tue May 30 07:36:25 2023,5,7,1,3.15,0.2,3.0,1.0,6.07,0.87,5.1,1.4,5.99,0.44,5.42,0.89,8.42,0.47,7.89
```