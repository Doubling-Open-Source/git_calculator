import datetime
from src.util import git_util
import os

def create_git_repo_with_timed_commits(directory_to_create_repo):

    # Ensure that directory_to_create_repo is a string representing a valid directory path
    if not isinstance(directory_to_create_repo, str) or not os.path.isdir(directory_to_create_repo):
        raise ValueError("Invalid directory path provided: "+str(directory_to_create_repo))

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

    # Make 12 commits, alternating between authors, with time intervals
    for i in range(1, 13):
        author_name, author_email = authors[i % len(authors)]

        # Calculate the commit and author date for this commit
        commit_date = start_date + datetime.timedelta(weeks=i-1)

        # Create a new file and add some content
        with open(f'file{i}.txt', 'w') as file:
            file.write(f'Commit {i} by {author_name}')

        # Stage the file and make the commit with specified dates
        git_util.git_run('add', f'file{i}.txt')
        git_util.git_run('commit', '-m', f'Commit {i} by {author_name}', '--author', f'{author_name} <{author_email}>', '--date', commit_date.strftime('%Y-%m-%dT%H:%M:%S'))


if __name__ == "__main__":
    create_git_repo_with_timed_commits()
