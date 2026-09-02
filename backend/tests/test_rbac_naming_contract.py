import inspect

from core.rbac import AbacPolicy, ResourceAction, evaluate_abac_policy


def test_abac_policy_uses_semantic_owned_field_names_with_legacy_aliases():
    """ABAC domain fields are semantic while legacy wire names remain compatible."""
    assert "resource_action" in AbacPolicy.model_fields
    assert "access_conditions" in AbacPolicy.model_fields
    assert "action" not in AbacPolicy.model_fields
    assert "conditions" not in AbacPolicy.model_fields

    abac_policy = AbacPolicy(
        policy_id="policy-1",
        resource_type="document",
        resource_action=ResourceAction.READ,
        access_conditions={"department": "sales"},
    )

    assert abac_policy.resource_action is ResourceAction.READ
    assert abac_policy.access_conditions == {"department": "sales"}
    assert abac_policy.action is ResourceAction.READ
    assert abac_policy.conditions == {"department": "sales"}
    assert abac_policy.model_dump(by_alias=True) == {
        "policy_id": "policy-1",
        "resource_type": "document",
        "action": ResourceAction.READ,
        "conditions": {"department": "sales"},
    }


def test_abac_policy_accepts_legacy_alias_input_without_making_it_internal_authority():
    """Existing action/conditions payloads deserialize at the compatibility boundary."""
    abac_policy = AbacPolicy(
        policy_id="policy-2",
        resource_type="document",
        action=ResourceAction.WRITE,
        conditions={"clearance": "high"},
    )

    assert abac_policy.resource_action is ResourceAction.WRITE
    assert abac_policy.access_conditions == {"clearance": "high"}


def test_abac_evaluator_parameter_and_reads_use_bounded_context_vocabulary():
    """The evaluator owns an explicit ABAC-policy parameter rather than bare policy."""
    assert "abac_policy" in inspect.signature(evaluate_abac_policy).parameters
    assert "policy" not in inspect.signature(evaluate_abac_policy).parameters

    abac_policy = AbacPolicy(
        policy_id="policy-3",
        resource_type="document",
        resource_action=ResourceAction.READ,
        access_conditions={"department": "sales"},
    )
    assert evaluate_abac_policy({"department": "sales"}, abac_policy) is True
