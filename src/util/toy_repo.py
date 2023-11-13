import datetime
from src.util import git_util
import os
import logging

# TODO: Refactor this next 
def create_git_repo_with_timed_commits_and_branches(directory_to_create_repo):

    # Ensure that directory_to_create_repo is a string representing a valid directory path
    if not isinstance(directory_to_create_repo, str) or not os.path.isdir(directory_to_create_repo):
        raise ValueError("Invalid directory path provided: " + str(directory_to_create_repo))

    # Change to the temporary directory provided
    os.chdir(directory_to_create_repo)

    # Initialize a new Git repository
    git_util.git_run('init')

    # Define a list of authors
    authors = [
        ('Author 1', 'author1@example.com'),
        ('Author 2', 'author2@example.com'),
        ('Author 3', 'author3@example.com'),
        ('Author 4', 'author4@example.com'),
    ]

    # Start date for commits (September 1, 2023)
    start_date = datetime.datetime(2023, 9, 1)

    # Simulate team workflow for 12 iterations
    for i in range(1, 13):
        author_name, author_email = authors[i % len(authors)]
        commit_date = start_date + datetime.timedelta(weeks=i - 1)
        topic_branch_name = f'topic-branch-{i}'
        git_util.git_run('checkout', '-b', topic_branch_name)

        with open(f'file{i}.txt', 'w') as file:
            file.write(f'Commit {i} by {author_name}')

        git_util.git_run('add', f'file{i}.txt')

        # Modify commit message to include 'bugfix' or 'hotfix' at certain intervals
        commit_msg = f"Commit {i} by {author_name}"
        if i % 4 == 0:  # Every 4th commit
            commit_msg += " - hotfix"
        elif i % 3 == 0:  # Every 3rd commit
            commit_msg += " - bugfix"

        git_util.git_run('commit', '-m', commit_msg, '--author', f'{author_name} <{author_email}>', '--date', commit_date.strftime('%Y-%m-%dT%H:%M:%S'))

        git_util.git_run('checkout', 'main')
        git_util.git_run('merge', topic_branch_name)


class ToyRepoCreator:
    """
    A utility class for creating and managing a Git repository with custom commit patterns.

    This class allows for initializing a new Git repository in a specified directory 
    and creating commits with configurable time intervals and authors. It supports 
    creating both evenly and unevenly spaced commits.

    Attributes:
        directory (str): The directory where the Git repository will be initialized.
        authors (list of tuple): A list of authors (name, email) to be used for commits.
        start_date (datetime): The starting date for the first commit.

    Methods:
        initialize_repo(): Initializes a new Git repository in the specified directory.
        create_commit(file_index, author_name, author_email, commit_date):
            Creates a commit in the repository.
        create_custom_commits(commit_intervals): Creates multiple commits in the 
            repository based on provided intervals.

    # Example usage
    creator = ToyRepoCreator('/path/to/repo')
    even_intervals = [7 * i for i in range(12)]  # Weekly intervals
    uneven_intervals = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]  # Exponential intervals

    creator.create_custom_commits(even_intervals)
    # or
    creator.create_custom_commits(uneven_intervals)
    """

    def __init__(self, directory):
        self.directory = directory
        self.authors = [
            ('Author 1', 'author1@example.com'),
            ('Author 2', 'author2@example.com'),
            ('Author 3', 'author3@example.com'),
            ('Author 4', 'author4@example.com'),
        ]
        self.start_date = datetime.datetime(2023, 9, 1)

    def initialize_repo(self):
        os.chdir(self.directory)
        git_util.git_run('init')

    def create_commit(self, file_index, author_name, author_email, commit_date):
        filename = f'file{file_index}.txt'

        with open(filename, 'w') as file:
            file.write(f'Commit {file_index} by {author_name}')

        git_util.git_run('add', filename)

        formatted_date = commit_date.strftime('%Y-%m-%dT%H:%M:%S')
        os.environ['GIT_COMMITTER_DATE'] = formatted_date
        os.environ['GIT_AUTHOR_DATE'] = formatted_date

        # Modify commit message to include 'bugfix' or 'hotfix'
        commit_msg = f"Commit {file_index} by {author_name}"
        if file_index % 4 == 0:  # Every 4th commit
            commit_msg += " - hotfix"
        elif file_index % 3 == 0:  # Every 3rd commit
            commit_msg += " - bugfix"

        git_util.git_run('commit', '-m', commit_msg, '--author', f'{author_name} <{author_email}>')

        del os.environ['GIT_COMMITTER_DATE']
        del os.environ['GIT_AUTHOR_DATE']

    def create_custom_commits(self, commit_intervals):
        self.initialize_repo()

        for i, interval in enumerate(commit_intervals, start=1):
            logging.debug('======= i =======: \n%s', i)
            author_name, author_email = self.authors[i % len(self.authors)]
            logging.debug('======= author_name =======: \n%s', author_name)
            logging.debug('======= author_email =======: \n%s', author_email)
            commit_date = self.start_date + datetime.timedelta(days=interval)
            logging.debug('======= commit_date =======: \n%s', commit_date)
            self.create_commit(i, author_name, author_email, commit_date)


    def create_custom_commits_single_author(self, commit_intervals):
        self.initialize_repo()

        for i, interval in enumerate(commit_intervals, start=1):
            logging.debug('======= i =======: \n%s', i)
            author_name, author_email = self.authors[0][0], self.authors[0][1]  
            logging.debug('======= author_name =======: \n%s', author_name)
            logging.debug('======= author_email =======: \n%s', author_email)
            commit_date = self.start_date + datetime.timedelta(days=interval)
            logging.debug('======= commit_date =======: \n%s', commit_date)
            self.create_commit(i, author_name, author_email, commit_date)
