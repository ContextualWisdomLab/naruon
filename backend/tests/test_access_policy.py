import pytest

from services.access_policy import (
    AccessRequest,
    ResourcePolicy,
    _is_system_admin_role,
    evaluate_access,
)


@pytest.mark.parametrize(
    "role,expected",
    [
        ("system_admin", True),
        ("platform_admin", True),
        ("tenant_admin", False),
        ("organization_admin", False),
        ("group_admin", False),
        ("member", False),
        ("unknown_role", False),
        ("", False),
    ],
)
def test_is_system_admin_role(role: str, expected: bool):
    assert _is_system_admin_role(role) is expected


def test_abac_organization_denial_precedes_role_and_group_allow():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="tenant_admin",
            organization_id="org-other",
            group_ids=("exec",),
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
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "organization_denied"


def test_abac_data_region_denial_overrides_system_admin_rbac_allow():
    decision = evaluate_access(
        AccessRequest(
            user_id="root",
            role="system_admin",
            organization_id="org-acme",
            group_ids=("exec",),
            data_region="us",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("system_admin",),
            permitted_group_ids=("exec",),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "data_region_denied"


def test_unrestricted_resource_data_region_allows_request_region():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="member",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=(),
            data_region=None,
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_workspace_denial_precedes_data_region_and_ownership_allow():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="member",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
            workspace_id="workspace-alpha",
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
            workspace_id="workspace-beta",
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "workspace_denied"


def test_missing_request_data_region_denies_regional_resource():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="member",
            organization_id="org-acme",
            group_ids=(),
            data_region=None,
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "data_region_denied"


def test_system_admin_cannot_bypass_organization_when_role_permitted():
    decision = evaluate_access(
        AccessRequest(
            user_id="root",
            role="system_admin",
            organization_id=None,
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("system_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "organization_denied"


def test_system_admin_cannot_bypass_ownership_when_role_permitted():
    decision = evaluate_access(
        AccessRequest(
            user_id="root",
            role="system_admin",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("system_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "ownership_denied"


def test_system_admin_can_access_owned_self_service_resource_when_owner_required():
    decision = evaluate_access(
        AccessRequest(
            user_id="root",
            role="system_admin",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="root",
            organization_id="org-acme",
            permitted_roles=("system_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
            require_owner_match=True,
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_system_admin_without_rbac_permission_is_denied():
    decision = evaluate_access(
        AccessRequest(
            user_id="root",
            role="system_admin",
            organization_id=None,
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("tenant_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "rbac_denied"


def test_tenant_admin_satisfies_member_role_hierarchy_for_owned_resource():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="tenant_admin",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_organization_admin_alias_satisfies_group_admin_hierarchy():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="organization_admin",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("group_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_tenant_admin_satisfies_organization_admin_alias_deterministically():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="tenant_admin",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("organization_admin",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_abac_owner_denial_overrides_group_admin_rbac_allow_without_delegation():
    decision = evaluate_access(
        AccessRequest(
            user_id="bob",
            role="group_admin",
            organization_id="org-acme",
            group_ids=("sales",),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("group_admin",),
            permitted_group_ids=("sales",),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "ownership_denied"


def test_abac_consent_denial_overrides_member_rbac_allow():
    decision = evaluate_access(
        AccessRequest(
            user_id="alice",
            role="member",
            organization_id="org-acme",
            group_ids=(),
            data_region="eu",
            consent_scopes=("calendar.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=(),
            data_region="eu",
            required_consent_scopes=("mail.read",),
        ),
    )

    assert decision.allowed is False
    assert decision.reason == "consent_denied"


def test_abac_delegation_allows_non_owner_after_all_denials_clear():
    decision = evaluate_access(
        AccessRequest(
            user_id="delegate",
            role="member",
            organization_id="org-acme",
            group_ids=("assistants",),
            data_region="eu",
            consent_scopes=("mail.read",),
        ),
        ResourcePolicy(
            owner_id="alice",
            organization_id="org-acme",
            permitted_roles=("member",),
            permitted_group_ids=("assistants",),
            data_region="eu",
            required_consent_scopes=("mail.read",),
            delegated_user_ids=("delegate",),
        ),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"
