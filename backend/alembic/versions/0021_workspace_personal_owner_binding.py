"""add fail-closed personal owner binding to the workspace registry

Revision ID: 0021_workspace_personal_owner_binding
Revises: 0020_workspace_organization_binding
Create Date: 2026-09-15 00:51:00.000000

Personal workspaces have ``organization_id IS NULL`` and therefore cannot use
organization binding as their membership evidence. ``workspace_id`` is opaque,
so identifier shape such as ``workspace-<user_id>`` is not ownership evidence.
This revision adds a nullable ``owner_user_id`` slot for trusted runtime
establishment while deliberately leaving historical rows unbound: the current
schema contains no auditable persisted user owner from which to backfill them.

The registry may be unbound, organization-bound, or personal-user-bound, but it
must never be bound to both an organization and a personal user at once.
Downgrade removes the column only when no personal ownership provenance has
been written; otherwise it fails closed rather than destroying that evidence.
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_workspace_personal_owner_binding"
down_revision = "0020_workspace_organization_binding"
branch_labels = None
depends_on = None

_ENTITIES_TABLE = "workspace_entities"
_OWNER_USER_COLUMN = "owner_user_id"
_OWNER_USER_INDEX = "ix_workspace_entities_owner_user_id"
_SCOPE_OWNER_CHECK = "ck_workspace_entities_single_scope_owner"


def upgrade() -> None:
    """Add personal-owner evidence without guessing ownership for legacy rows."""

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ENTITIES_TABLE):
        raise RuntimeError(
            "workspace_entities must exist before personal workspace binding"
        )

    entity_columns = {
        column["name"] for column in inspector.get_columns(_ENTITIES_TABLE)
    }
    if "organization_id" not in entity_columns:
        raise RuntimeError(
            "organization_id binding must exist before personal workspace binding"
        )
    if _OWNER_USER_COLUMN not in entity_columns:
        op.add_column(
            _ENTITIES_TABLE,
            sa.Column(_OWNER_USER_COLUMN, sa.String(), nullable=True),
        )

    inspector = sa.inspect(connection)
    index_names = {
        index["name"]
        for index in inspector.get_indexes(_ENTITIES_TABLE)
        if index.get("name")
    }
    if _OWNER_USER_INDEX not in index_names:
        op.create_index(
            _OWNER_USER_INDEX,
            _ENTITIES_TABLE,
            [_OWNER_USER_COLUMN],
        )

    check_names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(_ENTITIES_TABLE)
        if constraint.get("name")
    }
    if _SCOPE_OWNER_CHECK not in check_names:
        op.create_check_constraint(
            _SCOPE_OWNER_CHECK,
            _ENTITIES_TABLE,
            "NOT (organization_id IS NOT NULL AND owner_user_id IS NOT NULL)",
        )


def downgrade() -> None:
    """Remove the owner column only while it carries no security provenance."""

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ENTITIES_TABLE):
        return

    entity_columns = {
        column["name"] for column in inspector.get_columns(_ENTITIES_TABLE)
    }
    if _OWNER_USER_COLUMN not in entity_columns:
        return

    owner_count = connection.execute(
        sa.text(
            "SELECT count(*) FROM workspace_entities "
            "WHERE owner_user_id IS NOT NULL"
        )
    ).scalar_one()
    if owner_count:
        raise RuntimeError(
            "cannot downgrade personal workspace binding while owner provenance exists"
        )

    check_names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(_ENTITIES_TABLE)
        if constraint.get("name")
    }
    if _SCOPE_OWNER_CHECK in check_names:
        op.drop_constraint(
            _SCOPE_OWNER_CHECK,
            _ENTITIES_TABLE,
            type_="check",
        )

    inspector = sa.inspect(connection)
    index_names = {
        index["name"]
        for index in inspector.get_indexes(_ENTITIES_TABLE)
        if index.get("name")
    }
    if _OWNER_USER_INDEX in index_names:
        op.drop_index(_OWNER_USER_INDEX, table_name=_ENTITIES_TABLE)
    op.drop_column(_ENTITIES_TABLE, _OWNER_USER_COLUMN)
