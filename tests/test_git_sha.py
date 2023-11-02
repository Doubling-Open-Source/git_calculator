from src.git_ir import git_sha

def test_gitsha_creation():
    # Test creating gitsha instances
    sha1 = git_sha("abcdef1234")
    sha2 = git_sha("abcdef5678")

    # Check if instances are of the gitsha class
    assert isinstance(sha1, git_sha)
    assert isinstance(sha2, git_sha)

def test_gitsha_display_length():
    # Test the default display length
    sha = git_sha("abcdef1234")
    assert str(sha) == "abcd"

    # Test custom display length
    sha._show_ = 6
    assert str(sha) == "abcdef"

def test_gitsha_calibrate_min():
    # Create gitsha instances with common prefixes
    sha1_value = "abcdef1234"
    sha2_value = "abcdef5678"
    sha1 = git_sha(sha1_value)
    sha2 = git_sha(sha2_value)

    # Calibrate the display length
    git_sha.calibrate_min()

    # Re-fetch the instances from the class after the calibration
    sha1_updated = git_sha.get_instance(sha1_value)
    sha2_updated = git_sha.get_instance(sha2_value)

    # Now check the updated _show_ values
    assert sha1_updated._show_ == 7
    assert sha2_updated._show_ == 7

