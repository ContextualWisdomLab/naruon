import pytest

from runner.local_dav_adapters import LocalDavAdapters


def test_safe_target_path_decodes_url_encoded_path_traversals():
    adapter = LocalDavAdapters([])

    assert adapter._safe_target_path("/test/path") == "/test/path"

    assert adapter._safe_target_path("/test/%2e%2e/path") is None
    assert adapter._safe_target_path("/test/..%2fpath") is None
    assert adapter._safe_target_path("/%2e%2e/%2e%2e/etc/passwd") is None
    assert adapter._safe_target_path("/..%2f..%2fetc/passwd") is None


def test_safe_target_path_blocks_invalid_paths():
    adapter = LocalDavAdapters([])

    assert adapter._safe_target_path("test/path") is None
    assert adapter._safe_target_path("/test\\path") is None
    assert adapter._safe_target_path("http://example.com") is None
    assert adapter._safe_target_path(None) is None
