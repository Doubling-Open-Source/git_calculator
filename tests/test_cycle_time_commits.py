import pytest
import tempfile
import logging
import subprocess
from src.util import toy_repo  
import os
from src.calculators.cycle_time_by_commits_calculator import cycle_time_between_commits_by_author

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

    toy_repo.create_git_repo_with_timed_commits(temp_directory)
    #result = cycle_time_between_commits_by_author(os.path.join(temp_directory, 'test_output.csv'), bucket_size=4, window_size=2)
    result = cycle_time_between_commits_by_author(None, bucket_size=4, window_size=2)
    logging.debug('======= result =======: \n%s', result)