import pytest
import tempfile
import logging
import subprocess
from src.util.toy_repo import ToyRepoCreator 
import os
from src.calculators.cycle_time_by_commits_calculator import calculate_time_deltas, commit_statistics_to_string, commit_statistics_normalized_by_month
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


def test_cycle_time_normalized_by_month(temp_directory):

    trc = ToyRepoCreator(temp_directory)
    increasing_intervals = [10, 11, 12, 13, 34, 35, 41, 49, 60, 75, 80, 85]
    logging.debug('======= increasing_intervals =======: \n%s', increasing_intervals)
    trc.create_custom_commits_single_author(increasing_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics_normalized_by_month(tds)

    # Intermediary form
    #
    # [[(2023, 9), 
    # [[1694502000, 1440.0], 
    # [1694588400, 1440.0], 
    # [1694674800, 1440.0]]], 
    # [(2023, 10), 
    # [[1696489200, 30240.0], 
    # [1696575600, 1440.0], 
    # [1697094000, 8640.0], 
    # [1697785200, 11520.0], 
    # [1698735600, 15840.0]]], 
    # [(2023, 11), 
    # [[1700035200, 21600.0], 
    # [1700467200, 7200.0], 
    # [1700899200, 7200.0]]]]

    logging.debug('======= result =======: \n%s', result)
    # 1 day of minutes is: 60 minutes * 24 hours = 1440 minutes
    # For September:
        # The sum is: 4320 minutes
        # The average is: 1440 minutes
        # The 75th percentile is: 1440
        # The standard deviation is: 0 minutes
    # For October:
        # The sum is: 67680 minutes
        # The average is: 13536 minutes
        # The 75th percentile is: 15840
        # The standard deviation is: 10708 minutes
    # For November:
        # The sum is: 36000 minutes
        # The average is: 12000 minutes
        # The 75th percentile is: 14400
        # The standard deviation is: 8314 minutes




    expected= [((2023, 9), 
                    4320.0, 1440.0, 1440, 0), 
                ((2023, 10), 
                    67680.0, 13536.0, 15840, 10708), 
                ((2023, 11), 
                    36000.0, 12000.0, 14400, 8314)]
    
    assert result == expected, "Expected: %s, Actual: %s" % (expected, result)