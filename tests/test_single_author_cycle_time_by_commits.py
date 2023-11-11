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


def test_cycle_time_between_commits_single_author_no_deviation(temp_directory):
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
    even_intervals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    logging.debug('======= even_intervals =======: \n%s', even_intervals)
    trc.create_custom_commits_single_author(even_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    logging.debug('======= result =======: \n%s', result)
    # 1 day of minutes is: 60 minutes * 24 hours = 1440 minutes
    # 4 commits each with a cycle time of 1 day sums to: 5760 minutes
    # The average is: 1440 minutes
    # The 75th percentile is: 1440
    # The standard deviation is: 0 minutes

    expected= [('Sun Sep  3 00:00:00 2023', 5760.0, 1440.0, 1440, 0), 
               ('Thu Sep  7 00:00:00 2023', 5760.0, 1440.0, 1440, 0), 
               ('Mon Sep 11 00:00:00 2023', 4320.0, 1440.0, 1440, 0)]
    
    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)


def test_cycle_time_between_commits_single_author_small_deviation(temp_directory):
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
    # +1, +2, +3
    even_intervals = [1, 2, 4, 7, 8, 10, 13, 14, 16, 19, 20, 22]
    logging.debug('======= even_intervals =======: \n%s', even_intervals)
    trc.create_custom_commits_single_author(even_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    logging.debug('======= result =======: \n%s', result)
    # 1 day of minutes is: 60 minutes * 24 hours = 1440 minutes
    # First group:
    #   4 commits each with a cycle time of 1 + 2 + 3 + 1 or 7 days sums to: 10080 minutes
    #   [1440.0, 2880.0, 4320.0, 1440.0]
    #   The average is: 2520 minutes
    #   The 75th percentile is: 3240
    #   The standard deviations is: 1379
    # Second group:
    #   2 + 3 + 1 + 2 or 8 days sums to: 11520 minutes
    #   [2880.0, 4320.0, 1440.0, 2880.0]
    #   average is: 2880 minutes
    #   The 75th percentile is: 3240  
    #   Standard deviation is: 1176
    # Third group:
    #   3 + 1 + 2 or 6 days sums to: 8640 minutes
    #   [4320.0, 1440.0, 2880.0]
    #   average is: 2880 minutes
    #   The 75th percentile is: 3600
    #   The standard deviation is: 1440


    expected= [('Sun Sep  3 00:00:00 2023', 10080.0, 2520.0, 3240, 1379), 
               ('Mon Sep 11 00:00:00 2023', 11520.0, 2880.0, 3240, 1176), 
               ('Wed Sep 20 00:00:00 2023', 8640.0, 2880.0, 3600, 1440)]
    
    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)