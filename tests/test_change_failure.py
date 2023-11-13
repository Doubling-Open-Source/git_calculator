import pytest
import tempfile
import logging
import subprocess
from src.util.toy_repo import ToyRepoCreator 
import os
from src.calculators.change_failure_calculator import extract_commit_data, calculate_change_failure_rate
from src.git_ir import git_log

@pytest.fixture(scope="function")
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

@pytest.fixture(scope="function")
def temp_directory():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    subprocess.run(['rm', '-rf', temp_dir])

def test_change_failure_rate(temp_directory, setup_logging):
    """
    Tests the calculation of change failure rate in a toy repository.

    This function creates a toy repository with custom commits, some of which contain 'bugfix' or 'hotfix' in their messages.
    It then calculates the change failure rate for each month based on these commits.

    Args:
        temp_directory (str): A temporary directory path where the toy repository will be created.

    Asserts:
        The calculated change failure rates match the expected values.
    """
    trc = ToyRepoCreator(temp_directory)
    # Create custom commits with 'bugfix' and 'hotfix' in some commit messages
    trc.create_custom_commits([7 * i for i in range(12)])  # Weekly intervals for 12 weeks

    logs = git_log()
    commit_data = extract_commit_data(logs)
    change_failure_rates = calculate_change_failure_rate(commit_data)

    # Define expected change failure rates for each month
    # Assuming 'bugfix' or 'hotfix' appears in specific commits as per ToyRepoCreator logic
    expected_rates = {
        # Example expected values (update these based on actual ToyRepoCreator logic)
        '2023-9': 40,  
        '2023-10': 75,
        '2023-11': 33.3,
    }

    # Check if the calculated rates match the expected values
    for month, expected_rate in expected_rates.items():
        calculated_rate = change_failure_rates.get(month, 0)
        assert calculated_rate == expected_rate, f"Month: {month}, Expected: {expected_rate}, Actual: {calculated_rate}"

