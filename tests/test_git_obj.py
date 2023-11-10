import pytest
import tempfile
import logging
import subprocess
from src.util.toy_repo import ToyRepoCreator
from src.git_ir import all_objects, git_obj, git_log
from src.util.git_util import git_run
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

def test_new_object_creation(temp_directory):
    """
    Test the __new__ method to ensure no duplicate objects are created for the same SHA.
    """
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    res = git_run('log')


def test_all_objects(temp_directory):
    """
    Test the all_objects() method.
    """
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    result = all_objects()

    logging.debug('======= all_objects =======: \n%s', result)
    # Assert that the result is a list
    assert isinstance(result, list)

    # Assert that the result is not empty
    assert result

def test_git_log(temp_directory):
    """
    Test the git_log() method.
    """
    trc = ToyRepoCreator(temp_directory)
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    trc.create_custom_commits(even_intervals)
    commit_history = git_log()
    # print the result
    logging.debug('======= commit_history =======: \n%s', commit_history)
    # Perform assertions on the result
    assert isinstance(commit_history, list)
    assert len(commit_history) > 0