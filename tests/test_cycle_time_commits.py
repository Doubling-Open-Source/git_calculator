import pytest
import tempfile
import logging
import subprocess
from src.util.toy_repo import ToyRepoCreator 
import os
from src.calculators.cycle_time_by_commits_calculator import commit_statistics, calculate_time_deltas
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

    #toy_repo.create_git_repo_with_timed_commits(temp_directory)
    #result = cycle_time_between_commits_by_author(os.path.join(temp_directory, 'test_output.csv'), bucket_size=4, window_size=2)
    #result = cycle_time_between_commits_by_author(None, bucket_size=4, window_size=2)
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    logs = git_log()
    tds = calculate_time_deltas(logs)
    result = commit_statistics(tds, bucket_size=4)
    logging.debug('======= result =======: \n%s', result)
    # 4 week if minutes is: 60 minutes * 24 hours * 7 days * 4 weeks = 40320 minutes
    # 4 commits each with a cycle time of 4 weeks sums to: 161280 minutes
    # The average is: 40320 minutes
    # The 75th percentile of 4 commits each with a cycle time of 40320 minutes is: 
    # The standard deviation is: 0 minutes
    logging.debug("-----------------p75-----------------: \n%s", np.percentile([40320, 40320, 40320, 40320], 75))