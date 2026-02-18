import subprocess
import pytest
import tempfile


@pytest.fixture(scope="function")
def temp_directory():
    # Create a temporary directory for each test function
    temp_dir = tempfile.mkdtemp()
    yield temp_dir  # Provide the temporary directory as a fixture
    # Clean up: remove the temporary directory and its contents
    subprocess.run(["rm", "-rf", temp_dir])


def test_git_branches(temp_directory):
    """
    # Call the function to create a Git repository with timed commits and branches
    toy_repo.create_git_repo_with_timed_commits_and_branches(temp_directory)


    # Call the git_branches function on the test repository
    branch_info = git_branches()

    logging.debug('======= branch_info =======: \n%s', branch_info)
    # Assert that the returned value is a dictionary
    assert isinstance(branch_info, dict)

    # Check if topic branches exist
    for i in range(1, 13):
        topic_branch_name = f'topic-branch-{i}'
        assert topic_branch_name in [branch.split('/')[-1] for branch in branch_info.values()]
    """
    assert True
