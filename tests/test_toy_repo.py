import subprocess
import tempfile
import pytest
import logging
from src.util.toy_repo import ToyRepoCreator  
from src.util import git_util
import os

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

def test_create_git_repo(temp_directory):
    # Call the function to be tested
    
    logging.debug('======= temp_directory =======: \n%s', temp_directory)
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    res = git_util.git_run('log')
    logging.debug('======= res.stdout =======: \n%s', res.stdout)