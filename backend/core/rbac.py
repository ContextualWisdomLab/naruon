import enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from api.auth import RoleName


class ResourceAction(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class AbacPolicy(BaseModel):
    """Attribute-based access policy with semantic internal identifiers."""

    model_config = ConfigDict(populate_by_name=True)

    policy_id: str
    resource_type: str
    resource_action: ResourceAction = Field(alias="action")
    access_conditions: Dict[str, Any] = Field(alias="conditions")

    @property
    def action(self) -> ResourceAction:
        """Compatibility adapter for the historical public attribute name."""
        return self.resource_action

    @property
    def conditions(self) -> Dict[str, Any]:
        """Compatibility adapter for the historical public attribute name."""
        return self.access_conditions


def check_tenant_access(user_role: RoleName, required_role: RoleName) -> bool:
    """
    Check if the user's role satisfies the required role.
    Higher privileges include lower privileges.
    Universal mapping:
    - system_admin/platform_admin: SaaS Provider / System Admin
    - tenant_admin/organization_admin: Corporate Admin / Tenant Owner
    - group_admin: IT Operator / Department Head
    - member: B2B2C User or B2C Individual
    """
    hierarchy = {
        "member": 0,
        "group_admin": 1,
        "tenant_admin": 2,
        "organization_admin": 2,
        "system_admin": 3,
        "platform_admin": 3,
    }

    if user_role not in hierarchy or required_role not in hierarchy:
        return False

    return hierarchy[user_role] >= hierarchy[required_role]


def evaluate_abac_policy(
    user_attributes: Dict[str, Any], abac_policy: AbacPolicy
) -> bool:
    """Evaluate Attribute-Based Access Control policy conditions."""
    for key, expected_value in abac_policy.access_conditions.items():
        if user_attributes.get(key) != expected_value:
            return False
    return True
