"""Console script entry point for git-calculator."""

from importlib.metadata import entry_points


def test_console_script_entry_point():
    selected = entry_points(group="console_scripts")
    matches = [ep for ep in selected if ep.name == "git-calculator"]
    assert matches, "git-calculator console script is not installed"
    assert matches[0].value == "git_calculator.cli:main"
