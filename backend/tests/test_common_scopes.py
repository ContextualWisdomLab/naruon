from sqlalchemy.sql.selectable import Select

from api.auth import AuthContext
from api.common.scopes import connector_scope_statement


def test_connector_scope_statement_with_org():
    auth_context = AuthContext(
        user_id="test_user",
        role="member",
        organization_id="test_org_id",
        group_ids=(),
        workspace_id="test_workspace_id",
    )

    stmt = connector_scope_statement(auth_context)

    assert stmt is not None
    assert isinstance(stmt, Select)

    compiled = stmt.compile()
    params = compiled.params
    organization_parameter = next(
        value for key, value in params.items() if key.startswith("organization_id")
    )
    workspace_parameter = next(
        value for key, value in params.items() if key.startswith("workspace_id")
    )

    assert organization_parameter == auth_context.organization_id
    assert workspace_parameter == auth_context.workspace_id


def test_connector_scope_statement_without_org():
    auth_context = AuthContext(
        user_id="test_user",
        role="member",
        organization_id=None,
        group_ids=(),
        workspace_id="test_workspace_id",
    )

    stmt = connector_scope_statement(auth_context)
    assert stmt is None
