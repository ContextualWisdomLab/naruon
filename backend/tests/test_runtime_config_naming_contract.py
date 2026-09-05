from api.runtime_config import RuntimeConfigResponse


def test_runtime_config_uses_semantic_internal_fields_and_legacy_wire_aliases():
    assert set(RuntimeConfigResponse.model_fields) == {
        "product_name",
        "product_version",
        "feature_flags",
    }

    runtime_config = RuntimeConfigResponse(
        product_name="Naruon",
        product_version="1.2.3",
        feature_flags={"llm_enabled": True},
    )

    assert runtime_config.product_version == "1.2.3"
    assert runtime_config.feature_flags == {"llm_enabled": True}
    assert runtime_config.model_dump(by_alias=True) == {
        "product_name": "Naruon",
        "version": "1.2.3",
        "features": {"llm_enabled": True},
    }

    legacy_payload = RuntimeConfigResponse.model_validate(
        {
            "product_name": "Naruon",
            "version": "1.2.3",
            "features": {"llm_enabled": True},
        }
    )
    assert legacy_payload.product_version == "1.2.3"
    assert legacy_payload.feature_flags == {"llm_enabled": True}
