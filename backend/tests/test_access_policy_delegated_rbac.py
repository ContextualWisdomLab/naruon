from services.access_policy import AccessRequest, ResourcePolicy, evaluate_access


def test_delegated_user_without_role_or_group_permission_is_rbac_denied():
    """Delegation clears ownership, but does not bypass the final RBAC gate."""
    decision = evaluate_access(
        AccessRequest(
            user_id="delegate",
            role="member",
            organization_id="org-acme",
            group_ids=("sales",),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("tenant_admin",),
            permitted_group_ids=("exec",),
            data_region="eu",
            required_consent_scopes=("mail.read",),
            delegated_user_ids=("delegate",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "rbac_denied"
