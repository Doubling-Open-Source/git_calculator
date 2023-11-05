import pytest
import tempfile
import logging
import subprocess
from src.util import toy_repo  
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
    toy_repo.create_git_repo_with_timed_commits(temp_directory)
    res = git_run('log')


def test_all_objects(temp_directory):
    """
    Test the all_objects() method.
    """
    toy_repo.create_git_repo_with_timed_commits(temp_directory)
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
    toy_repo.create_git_repo_with_timed_commits(temp_directory)
    # Change to the temporary directory provided
    os.chdir(temp_directory)
    commit_history = git_log()
    # print the result
    logging.debug('======= commit_history =======: \n%s', commit_history)
    # Perform assertions on the result
    assert isinstance(commit_history, list)
    assert len(commit_history) > 0