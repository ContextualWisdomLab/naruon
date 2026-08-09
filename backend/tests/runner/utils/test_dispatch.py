from runner.utils.dispatch import dispatch_error

def test_dispatch_error():
    """Test that dispatch_error constructs the payload correctly."""
    error_code = "TEST_ERROR_123"
    payload = dispatch_error(error_code)

    assert payload == {
        "status": "error",
        "error": error_code,
        "error_code": error_code,
        "provider_write_executed": False,
    }
