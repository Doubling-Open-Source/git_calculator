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


def test_cycle_time_between_commits_by_author_no_deviation(temp_directory):
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
    logging.debug('======= even_intervals =======: \n%s', even_intervals)
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

def test_cycle_time_between_commits_by_author_no_deviation_clustered(temp_directory):
    """
    Tests the calculation of cycle time between git commits by authors in a toy repository, 
    expecting a small standard deviation in the results.

    This function creates a toy repository in a temporary directory using the ToyRepoCreator class.
    It generates custom commits with slightly varying intervals, close to a specific time period (e.g., weekly),
    to create a small standard deviation in commit cycle times. The git log is retrieved and used to calculate 
    time deltas between commits, which are then used to compute commit statistics with a specified bucket size.

    The test verifies the statistics generated against expected values. These values include the sum,
    average, 75th percentile, and standard deviation of the commit cycle times in minutes, where the 
    standard deviation is expected to be small due to the similar cycle times of the commits.

    Args:
        temp_directory (str): A temporary directory path where the toy repository will be created.

    Raises:
        AssertionError: If the calculated commit statistics do not match the expected values.
    """
    trc = ToyRepoCreator(temp_directory)
    # Slightly varying intervals around 7 days: 6, 7, 8 days
    varied_intervals = [6 + i % 3 for i in range(12)] 
    # [6, 7, 8, 6, 7, 8, 6, 7, 8, 6, 7, 8]
    logging.debug('======= varied_intervals =======: \n%s', varied_intervals)
    trc.create_custom_commits(varied_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    logging.debug('======= result =======: \n%s', result)

    # 1 day of minutes is: 60 minutes * 24 hours = 1440 minutes
    # 4 commits each with a cycle time of 1 day sums to: 5760 minutes per batch
    # The average is: 1440 minutes
    # The 75th percentile is: 1440
    # The standard deviation is: 0 minutes

    expected = [('Fri Sep  8 00:00:00 2023', 5760.0, 1440.0, 1440, 0), ('Sat Sep  9 00:00:00 2023', 5760.0, 1440.0, 1440, 0)]

    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)


def test_cycle_time_between_commits_by_author_small_deviation(temp_directory):
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
    # +10, +1, +4
    small_deviation_intervals = [1, 10, 11, 15, 25, 26, 30, 40, 41, 45, 55, 56]
    logging.debug('======= even_intervals =======: \n%s', small_deviation_intervals)
    trc.create_custom_commits(small_deviation_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    # 4 week of minutes is: 60 minutes * 24 hours * 7 days * 4 weeks = 40320 minutes
    # 4 commits each with a cycle time of 4 weeks sums to: 161280 minutes
    # The average is: 40320 minutes
    # The 75th percentile of 4 commits each with a cycle time of 40320 minutes is: 40320
    # The standard deviation is: 0 minutes

    logging.debug('======= result =======: \n%s', result)

    expected = [('Tue Sep 26 00:00:00 2023', 120960.0, 30240.0, 34920, 6109), ('Thu Oct 12 00:00:00 2023', 109440.0, 27360.0, 29520, 6109)]

    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)


def test_cycle_time_between_commits_by_author_high_deviation(temp_directory):
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
    small_deviation_intervals = [1, 18, 40, 157, 255, 256, 257, 398, 431, 432, 433, 434]
    logging.debug('======= even_intervals =======: \n%s', small_deviation_intervals)
    trc.create_custom_commits(small_deviation_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    # 4 week of minutes is: 60 minutes * 24 hours * 7 days * 4 weeks = 40320 minutes
    # 4 commits each with a cycle time of 4 weeks sums to: 161280 minutes
    # The average is: 40320 minutes
    # The 75th percentile of 4 commits each with a cycle time of 40320 minutes is: 40320
    # The standard deviation is: 0 minutes

    logging.debug('======= result =======: \n%s', result)

    expected = [('Mon May 13 00:00:00 2024', 1368000.0, 342000.0, 351720, 22075), ('Tue Nov  5 00:00:00 2024', 812160.0, 203040.0, 253440, 100800)]

    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)

def test_cycle_time_between_commits_single_author_high_deviation(temp_directory):
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
    small_deviation_intervals = [1, 18, 40, 157, 255, 256, 257, 398, 431, 432, 433, 434]
    logging.debug('======= even_intervals =======: \n%s', small_deviation_intervals)
    trc.create_custom_commits_single_author(small_deviation_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)

    # 4 week of minutes is: 60 minutes * 24 hours * 7 days * 4 weeks = 40320 minutes
    # 4 commits each with a cycle time of 4 weeks sums to: 161280 minutes
    # The average is: 40320 minutes
    # The 75th percentile of 4 commits each with a cycle time of 40320 minutes is: 40320
    # The standard deviation is: 0 minutes

    logging.debug('======= result =======: \n%s', result)

    expected = [('Mon May 13 00:00:00 2024', 1368000.0, 342000.0, 351720, 22075), ('Tue Nov  5 00:00:00 2024', 812160.0, 203040.0, 253440, 100800)]

    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)
