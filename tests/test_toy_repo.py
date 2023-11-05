import subprocess
import tempfile
import pytest
import logging
from src.util import toy_repo  
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
    toy_repo.create_git_repo_with_timed_commits(temp_directory)
    # Change to the temporary directory provided
    os.chdir(temp_directory)
    res = git_util.git_run('log')
    logging.debug('======= res.stdout =======: \n%s', res.stdout)