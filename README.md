# git-calculator
Calculate dora metrics and related from a Git repository on the local file system. Does not require integration with GitHub or any other git service provider.

# Project Outline

```
git-calculator/
│
├── src/
|   ├── git_util.py      # Helpers for interacting with a Git repo
|   ├── git_ir.py        # In memory representation of Git metadata
│   ├── calculators/
│   │   ├── cycle_time_calculator.py  # Cycle time calculation
│   │   └── variance_calculator.py    # Cycle time variance calculation
│
├── tests/
│   └── test_*.py        # Unit tests
│
├── README.md             # Documentation
├── requirements.txt      # Dependencies
└── setup.py              # Setup
```

# Project Usage

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

Run unit tests
```
pytest -v
```

For debugging:
```export PYTEST_ADDOPTS="--log-cli-level=DEBUG"```

To play around with the interpreter:
```
python
from src.util import toy_repo
toy_repo.create_git_repo_with_timed_commits("/Users/denalilumma/doubling-code/git-calculator/.scratch")
```
(Replace with your local path)

```
from src.calculators.cycle_time_by_commits_calculator import cycle_time_between_commits_by_author
result = cycle_time_between_commits_by_author(None, bucket_size=4, window_size=2)
print(result)
```