"""Packaging: git_calculator is the import package."""

from git_calculator.cli import main


def test_git_calculator_package_imports():
    import git_calculator

    assert git_calculator is not None


def test_cli_main_is_callable():
    assert callable(main)
