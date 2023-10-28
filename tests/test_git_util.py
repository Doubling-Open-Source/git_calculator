from src.util.git_util import gitsha

def test_gitsha_creation():
    # Test creating gitsha instances
    sha1 = gitsha("abcdef1234")
    sha2 = gitsha("abcdef5678")

    # Check if instances are of the gitsha class
    assert isinstance(sha1, gitsha)
    assert isinstance(sha2, gitsha)

def test_gitsha_display_length():
    # Test the default display length
    sha = gitsha("abcdef1234")
    assert str(sha) == "abcd"

    # Test custom display length
    sha._show_ = 6
    assert str(sha) == "abcdef"

def test_gitsha_calibrate_min():
    # Create gitsha instances with common prefixes
    sha1_value = "abcdef1234"
    sha2_value = "abcdef5678"
    sha1 = gitsha(sha1_value)
    sha2 = gitsha(sha2_value)

    # Calibrate the display length
    gitsha.calibrate_min()

    # Re-fetch the instances from the class after the calibration
    sha1_updated = gitsha.get_instance(sha1_value)
    sha2_updated = gitsha.get_instance(sha2_value)

    # Now check the updated _show_ values
    assert sha1_updated._show_ == 7
    assert sha2_updated._show_ == 7

