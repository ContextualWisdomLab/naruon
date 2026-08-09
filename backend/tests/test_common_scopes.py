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

    # Compile the statement to check the bound parameters
    compiled = stmt.compile()
    params = compiled.params

    # Parameters are typically like organization_id_1, workspace_id_1, param_1
    assert "test_org_id" in params.values()
    assert "test_workspace_id" in params.values()


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
