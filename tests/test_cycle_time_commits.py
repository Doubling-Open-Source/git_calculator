import pytest
import tempfile
import logging
import subprocess
from src.util.toy_repo import ToyRepoCreator 
import os
from src.calculators.cycle_time_by_commits_calculator import commit_statistics, calculate_time_deltas, commit_statistics_to_string
import numpy as np
from src.git_ir import git_log

@pytest.fixture(scope="function")
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,  # Set the desired log level
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

@pytest.fixture(scope="function")
def temp_directory():
    # Create a temporary directory for each test function
    temp_dir = tempfile.mkdtemp()
    yield temp_dir  # Provide the temporary directory as a fixture
    # Clean up: remove the temporary directory and its contents
    subprocess.run(['rm', '-rf', temp_dir])


def test_cycle_time_between_commits_by_author(temp_directory):
    """
    Tests the calculation of cycle time between git commits by authors in a toy repository.

    This function creates a toy repository in a temporary directory using the ToyRepoCreator class.
    It then generates custom commits at even weekly intervals (7 days apart) for a total of 12 weeks.
    The git log is retrieved and used to calculate time deltas between commits. These time deltas are
    then used to compute commit statistics with a specified bucket size.

    The test verifies the statistics generated against expected values. These values are the sum,
    average, 75th percentile, and standard deviation of the commit cycle times in minutes over the 
    period of 12 weeks. The expected results are calculated for commits with cycle times of 4 weeks each.

    Args:
        temp_directory (str): A temporary directory path where the toy repository will be created.

    Raises:
        AssertionError: If the calculated commit statistics do not match the expected values.
    """
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    # 4 week of minutes is: 60 minutes * 24 hours * 7 days * 4 weeks = 40320 minutes
    # 4 commits each with a cycle time of 4 weeks sums to: 161280 minutes
    # The average is: 40320 minutes
    # The 75th percentile of 4 commits each with a cycle time of 40320 minutes is: 40320
    # The standard deviation is: 0 minutes

    expected= [('Fri Sep 29 00:00:00 2023', 161280.0, 40320.0, 40320, 0), 
               ('Fri Oct 27 00:00:00 2023', 161280.0, 40320.0, 40320, 0)]
    
    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)

