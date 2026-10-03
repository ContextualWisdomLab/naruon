import pytest
from services.carddav_client import _resolved_global_addresses


def test_resolved_global_addresses_blocks_internal_domains():
    with pytest.raises(ValueError, match="invalid_carddav_url"):
        _resolved_global_addresses("localhost", 443)

    with pytest.raises(ValueError, match="invalid_carddav_url"):
        _resolved_global_addresses("test.localhost", 443)

    with pytest.raises(ValueError, match="invalid_carddav_url"):
        _resolved_global_addresses("internal", 443)

    with pytest.raises(ValueError, match="invalid_carddav_url"):
        _resolved_global_addresses("test.internal", 443)

    with pytest.raises(ValueError, match="invalid_carddav_url"):
        _resolved_global_addresses("test.local", 443)
