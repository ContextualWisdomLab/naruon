"""bind workspace registry rows to auditable organization evidence

Revision ID: 0020_workspace_organization_binding
Revises: 0019_email_read_state_repair
Create Date: 2026-09-14 20:41:00.000000

``workspace_id`` is an opaque authenticated claim, not an organization-derived
identifier. This revision therefore binds a workspace only when persisted
``workspace_documents.organization_id`` evidence is non-null and unambiguous:
exactly one distinct organization is already recorded for that workspace.
Ambiguous and evidence-free workspaces remain unbound so authorization can fail
closed instead of guessing an owner from an identifier shape.

Once a workspace is safely bound, legacy NULL document rows in that same
workspace inherit the binding. Downgrade is intentionally non-destructive:
these bindings are ownership provenance and cannot be distinguished later from
assignments written by normal application traffic.
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_workspace_organization_binding"
down_revision = "0019_email_read_state_repair"
branch_labels = None
depends_on = None

_ENTITIES_TABLE = "workspace_entities"
_DOCUMENTS_TABLE = "workspace_documents"
_ORGANIZATION_COLUMN = "organization_id"
_ORGANIZATION_INDEX = "ix_workspace_entities_organization_id"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ENTITIES_TABLE):
        raise RuntimeError(
            "workspace_entities must exist before workspace organization binding"
        )
    if not inspector.has_table(_DOCUMENTS_TABLE):
        raise RuntimeError(
            "workspace_documents must exist before workspace organization binding"
        )

    entity_columns = {
        column["name"] for column in inspector.get_columns(_ENTITIES_TABLE)
    }
    if _ORGANIZATION_COLUMN not in entity_columns:
        op.add_column(
            _ENTITIES_TABLE,
            sa.Column(_ORGANIZATION_COLUMN, sa.String(), nullable=True),
        )
    op.create_index(
        _ORGANIZATION_INDEX,
        _ENTITIES_TABLE,
        [_ORGANIZATION_COLUMN],
        if_not_exists=True,
    )

    workspace_entities = sa.table(
        _ENTITIES_TABLE,
        sa.column("workspace_id", sa.String()),
        sa.column(_ORGANIZATION_COLUMN, sa.String()),
    )
    workspace_documents = sa.table(
        _DOCUMENTS_TABLE,
        sa.column("workspace_id", sa.String()),
        sa.column(_ORGANIZATION_COLUMN, sa.String()),
    )

    ownership_evidence = (
        sa.select(
            workspace_documents.c.workspace_id.label("workspace_id"),
            sa.func.min(workspace_documents.c.organization_id).label(
                "organization_id"
            ),
            sa.func.count(sa.distinct(workspace_documents.c.organization_id)).label(
                "organization_count"
            ),
        )
        .where(workspace_documents.c.organization_id.is_not(None))
        .group_by(workspace_documents.c.workspace_id)
        .subquery()
    )
    unambiguous_evidence = (
        sa.select(
            ownership_evidence.c.workspace_id,
            ownership_evidence.c.organization_id,
        )
        .where(ownership_evidence.c.organization_count == 1)
        .subquery()
    )

    inferred_organization = (
        sa.select(unambiguous_evidence.c.organization_id)
        .where(
            unambiguous_evidence.c.workspace_id
            == workspace_entities.c.workspace_id
        )
        .correlate(workspace_entities)
        .scalar_subquery()
    )
    has_unambiguous_evidence = (
        sa.exists(
            sa.select(1)
            .select_from(unambiguous_evidence)
            .where(
                unambiguous_evidence.c.workspace_id
                == workspace_entities.c.workspace_id
            )
        )
        .correlate(workspace_entities)
    )
    connection.execute(
        sa.update(workspace_entities)
        .where(
            workspace_entities.c.organization_id.is_(None),
            has_unambiguous_evidence,
        )
        .values(organization_id=inferred_organization)
    )

    bound_organization = (
        sa.select(workspace_entities.c.organization_id)
        .where(
            workspace_entities.c.workspace_id == workspace_documents.c.workspace_id,
            workspace_entities.c.organization_id.is_not(None),
        )
        .correlate(workspace_documents)
        .scalar_subquery()
    )
    has_binding = (
        sa.exists(
            sa.select(1)
            .select_from(workspace_entities)
            .where(
                workspace_entities.c.workspace_id
                == workspace_documents.c.workspace_id,
                workspace_entities.c.organization_id.is_not(None),
            )
        )
        .correlate(workspace_documents)
    )
    connection.execute(
        sa.update(workspace_documents)
        .where(
            workspace_documents.c.organization_id.is_(None),
            has_binding,
        )
        .values(organization_id=bound_organization)
    )


def downgrade() -> None:
    # Binding/backfill turns ambiguous legacy NULLs into explicit ownership
    # provenance. A later downgrade cannot distinguish those values from normal
    # application assignments, so removing them or the column could destroy
    # security-relevant tenant evidence.
    return None
