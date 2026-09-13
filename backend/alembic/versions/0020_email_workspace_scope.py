"""add workspace_id scope column to email_records

Revision ID: 0020_email_workspace_scope
Revises: 0019_attachment_uid
Create Date: 2026-08-31 00:00:00.000000

Historical email workspace ownership is not derivable from organization_id.
Operators must supply verified workspace assignments through Alembic ``-x``
arguments when legacy rows exist. Online execution verifies that no unresolved
rows remain before enforcing NOT NULL. Offline SQL generation cannot inspect
row completeness, so it fails closed unless the operator supplies either a
validated fallback or explicitly attests that the per-email mapping is complete.
"""

import json

from alembic import context, op
import sqlalchemy as sa

revision = "0020_email_workspace_scope"
down_revision = "0019_attachment_uid"

_EMAIL_TABLE = "email_records"
_EMAIL_WORKSPACE_INDEX = "ix_email_records_workspace_id"
_OLD_EMAIL_IDENTITY = "uq_emails_owner_message_id"
# backend/scripts/bootstrap_db.py's dev-compat path predates this migration
# and creates the owner-only identity under a different name and as a plain
# index rather than a named unique constraint; a database bootstrapped before
# that script's own fix landed and later migrated via Alembic needs this
# shape recognized too, or it keeps the stricter, non-workspace-scoped
# identity forever.
_BOOTSTRAP_OLD_EMAIL_IDENTITY = "uq_email_records_owner_message_id"
_EMAIL_WORKSPACE_IDENTITY = "uq_emails_workspace_message"
_WORKSPACE_MAPPING_X_ARG = "email_workspace_mapping_json"
_WORKSPACE_FALLBACK_X_ARG = "email_workspace_fallback"
_WORKSPACE_MAPPING_COMPLETE_X_ARG = "email_workspace_mapping_complete"
_DOWNGRADE_IDENTITY_VERIFIED_X_ARG = "email_workspace_downgrade_owner_identity_verified"
_TRUE_VALUES = frozenset({"1", "true", "yes"})


def _email_table_stub() -> sa.TableClause:
    return sa.table(
        _EMAIL_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.String()),
        sa.column("organization_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("message_id", sa.String()),
    )


def _x_arguments() -> dict[str, str]:
    """Return Alembic ``-x`` values, including under direct migration tests."""
    try:
        values = context.get_x_argument(as_dictionary=True)
    except NameError:
        # ``Operations.context(MigrationContext(...))`` installs ``op`` but not
        # an EnvironmentContext proxy. Direct migration tests therefore have no
        # command-line ``-x`` arguments, which is equivalent to an empty set.
        return {}
    return {str(key): str(value) for key, value in values.items()}


def _validated_workspace_id(value: str, *, argument_name: str) -> str:
    normalized = value.strip()
    if not normalized or not normalized.isascii():
        raise RuntimeError(f"{argument_name} must be a non-empty ASCII workspace ID")
    return normalized


def _workspace_backfill_inputs() -> tuple[dict[int, str], str | None, bool]:
    arguments = _x_arguments()
    mapping: dict[int, str] = {}
    raw_mapping = arguments.get(_WORKSPACE_MAPPING_X_ARG)
    if raw_mapping:
        try:
            parsed_mapping = json.loads(raw_mapping)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{_WORKSPACE_MAPPING_X_ARG} must be a JSON object keyed by email row ID"
            ) from exc
        if not isinstance(parsed_mapping, dict):
            raise RuntimeError(
                f"{_WORKSPACE_MAPPING_X_ARG} must be a JSON object keyed by email row ID"
            )
        for raw_email_id, raw_workspace_id in parsed_mapping.items():
            try:
                email_id = int(raw_email_id)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"{_WORKSPACE_MAPPING_X_ARG} keys must be positive integer email row IDs"
                ) from exc
            if email_id <= 0 or not isinstance(raw_workspace_id, str):
                raise RuntimeError(
                    f"{_WORKSPACE_MAPPING_X_ARG} must map positive email row IDs to workspace IDs"
                )
            mapping[email_id] = _validated_workspace_id(
                raw_workspace_id,
                argument_name=_WORKSPACE_MAPPING_X_ARG,
            )

    fallback = arguments.get(_WORKSPACE_FALLBACK_X_ARG)
    if fallback is not None:
        fallback = _validated_workspace_id(
            fallback,
            argument_name=_WORKSPACE_FALLBACK_X_ARG,
        )

    mapping_complete = (
        arguments.get(_WORKSPACE_MAPPING_COMPLETE_X_ARG, "").strip().lower()
        in _TRUE_VALUES
    )
    return mapping, fallback, mapping_complete


def _apply_workspace_backfill(
    execute_statement,
    mapping: dict[int, str],
    fallback: str | None,
) -> None:
    emails = _email_table_stub()
    for email_id, workspace_id in sorted(mapping.items()):
        execute_statement(
            sa.update(emails)
            .where(
                emails.c.id == email_id,
                emails.c.workspace_id.is_(None),
            )
            .values(workspace_id=workspace_id)
        )
    if fallback is not None:
        execute_statement(
            sa.update(emails)
            .where(emails.c.workspace_id.is_(None))
            .values(workspace_id=fallback)
        )


def _emit_workspace_identity_upgrade() -> None:
    op.create_index(
        _EMAIL_WORKSPACE_INDEX,
        _EMAIL_TABLE,
        ["workspace_id"],
        if_not_exists=True,
    )
    for legacy_name in (_OLD_EMAIL_IDENTITY, _BOOTSTRAP_OLD_EMAIL_IDENTITY):
        op.drop_constraint(
            legacy_name,
            _EMAIL_TABLE,
            type_="unique",
            if_exists=True,
        )
        op.drop_index(
            legacy_name,
            table_name=_EMAIL_TABLE,
            if_exists=True,
        )
    op.create_unique_constraint(
        _EMAIL_WORKSPACE_IDENTITY,
        _EMAIL_TABLE,
        ["user_id", "organization_id", "workspace_id", "message_id"],
    )


def _emit_offline_upgrade() -> None:
    mapping, fallback, mapping_complete = _workspace_backfill_inputs()
    if fallback is None and not mapping_complete:
        raise RuntimeError(
            "Offline 0020 migration cannot verify historical workspace ownership. "
            f"Provide -x {_WORKSPACE_FALLBACK_X_ARG}=<operator-validated-workspace> "
            f"or a complete -x {_WORKSPACE_MAPPING_X_ARG}=<json> mapping together "
            f"with -x {_WORKSPACE_MAPPING_COMPLETE_X_ARG}=true."
        )

    op.add_column(
        _EMAIL_TABLE,
        sa.Column("workspace_id", sa.String(), nullable=True),
    )
    _apply_workspace_backfill(op.execute, mapping, fallback)
    # With an operator-validated fallback every remaining NULL is assigned.
    # With a complete-map attestation, PostgreSQL itself still rejects the
    # generated ALTER if the operator's mapping omitted an existing row.
    op.alter_column(_EMAIL_TABLE, "workspace_id", nullable=False)
    _emit_workspace_identity_upgrade()


def upgrade() -> None:
    if context.is_offline_mode():
        _emit_offline_upgrade()
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE):
        return

    existing_columns = {
        column["name"]: column for column in inspector.get_columns(_EMAIL_TABLE)
    }
    workspace_column = existing_columns.get("workspace_id")
    if workspace_column is None:
        op.add_column(
            _EMAIL_TABLE, sa.Column("workspace_id", sa.String(), nullable=True)
        )

    mapping, fallback, _mapping_complete = _workspace_backfill_inputs()
    _apply_workspace_backfill(connection.execute, mapping, fallback)

    emails = _email_table_stub()
    unresolved_count = connection.execute(
        sa.select(sa.func.count())
        .select_from(emails)
        .where(emails.c.workspace_id.is_(None))
    ).scalar_one()
    if unresolved_count:
        raise RuntimeError(
            f"{unresolved_count} historical email row(s) have no verified workspace. "
            f"Provide -x {_WORKSPACE_MAPPING_X_ARG}=<json> with authoritative email-ID "
            f"assignments, optionally plus -x {_WORKSPACE_FALLBACK_X_ARG}=<operator-validated-workspace>."
        )

    if workspace_column is None or workspace_column.get("nullable", True):
        op.alter_column(_EMAIL_TABLE, "workspace_id", nullable=False)

    existing_indexes = {index["name"] for index in inspector.get_indexes(_EMAIL_TABLE)}
    if _EMAIL_WORKSPACE_INDEX not in existing_indexes:
        op.create_index(
            _EMAIL_WORKSPACE_INDEX,
            _EMAIL_TABLE,
            ["workspace_id"],
            if_not_exists=True,
        )

    existing_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(_EMAIL_TABLE)
    }
    unique_indexes = {
        index["name"]
        for index in inspector.get_indexes(_EMAIL_TABLE)
        if index.get("unique")
    }
    # get_indexes() also reports the backing index of a unique constraint
    # under the same name (PostgreSQL implements a unique constraint via a
    # unique index), so each identity's constraint case must be checked --
    # and handled -- before its index case: DROP INDEX on a constraint's own
    # backing index is rejected by PostgreSQL ("cannot drop index ...
    # because constraint ... requires it"), which would abort this
    # migration outright.
    if _OLD_EMAIL_IDENTITY in existing_constraints:
        op.drop_constraint(_OLD_EMAIL_IDENTITY, _EMAIL_TABLE, type_="unique")
    elif _OLD_EMAIL_IDENTITY in unique_indexes:
        op.drop_index(_OLD_EMAIL_IDENTITY, table_name=_EMAIL_TABLE)

    if _BOOTSTRAP_OLD_EMAIL_IDENTITY in existing_constraints:
        op.drop_constraint(
            _BOOTSTRAP_OLD_EMAIL_IDENTITY, _EMAIL_TABLE, type_="unique"
        )
    elif _BOOTSTRAP_OLD_EMAIL_IDENTITY in unique_indexes:
        op.drop_index(_BOOTSTRAP_OLD_EMAIL_IDENTITY, table_name=_EMAIL_TABLE)

    if _EMAIL_WORKSPACE_IDENTITY not in existing_constraints | unique_indexes:
        op.create_unique_constraint(
            _EMAIL_WORKSPACE_IDENTITY,
            _EMAIL_TABLE,
            ["user_id", "organization_id", "workspace_id", "message_id"],
        )


def _offline_downgrade_is_operator_verified() -> bool:
    return (
        _x_arguments().get(_DOWNGRADE_IDENTITY_VERIFIED_X_ARG, "").strip().lower()
        in _TRUE_VALUES
    )


def _emit_offline_downgrade() -> None:
    if not _offline_downgrade_is_operator_verified():
        raise RuntimeError(
            "Offline 0020 downgrade cannot verify whether owner/message duplicates "
            "exist across workspaces. Verify that restoring the owner-only identity "
            f"is safe, then pass -x {_DOWNGRADE_IDENTITY_VERIFIED_X_ARG}=true."
        )

    op.drop_index(
        _EMAIL_WORKSPACE_INDEX,
        table_name=_EMAIL_TABLE,
        if_exists=True,
    )
    op.drop_constraint(
        _EMAIL_WORKSPACE_IDENTITY,
        _EMAIL_TABLE,
        type_="unique",
        if_exists=True,
    )
    op.drop_index(
        _EMAIL_WORKSPACE_IDENTITY,
        table_name=_EMAIL_TABLE,
        if_exists=True,
    )
    op.create_unique_constraint(
        _OLD_EMAIL_IDENTITY,
        _EMAIL_TABLE,
        ["user_id", "organization_id", "message_id"],
    )
    op.drop_column(_EMAIL_TABLE, "workspace_id", if_exists=True)


def downgrade() -> None:
    if context.is_offline_mode():
        _emit_offline_downgrade()
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE):
        return

    emails = _email_table_stub()
    duplicate_identity = connection.execute(
        sa.select(
            emails.c.user_id,
            emails.c.organization_id,
            emails.c.message_id,
        )
        .group_by(
            emails.c.user_id,
            emails.c.organization_id,
            emails.c.message_id,
        )
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicate_identity is not None:
        raise RuntimeError(
            "Cannot downgrade email workspace identity while duplicate owner/message "
            "rows exist across workspaces"
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes(_EMAIL_TABLE)}
    if _EMAIL_WORKSPACE_INDEX in existing_indexes:
        op.drop_index(_EMAIL_WORKSPACE_INDEX, table_name=_EMAIL_TABLE, if_exists=True)

    existing_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(_EMAIL_TABLE)
    }
    unique_indexes = {
        index["name"]
        for index in inspector.get_indexes(_EMAIL_TABLE)
        if index.get("unique")
    }
    if _EMAIL_WORKSPACE_IDENTITY in existing_constraints:
        op.drop_constraint(_EMAIL_WORKSPACE_IDENTITY, _EMAIL_TABLE, type_="unique")
    elif _EMAIL_WORKSPACE_IDENTITY in unique_indexes:
        op.drop_index(_EMAIL_WORKSPACE_IDENTITY, table_name=_EMAIL_TABLE)
    if _OLD_EMAIL_IDENTITY not in existing_constraints | unique_indexes:
        op.create_unique_constraint(
            _OLD_EMAIL_IDENTITY,
            _EMAIL_TABLE,
            ["user_id", "organization_id", "message_id"],
        )

    existing_columns = {
        column["name"] for column in inspector.get_columns(_EMAIL_TABLE)
    }
    if "workspace_id" in existing_columns:
        op.drop_column(_EMAIL_TABLE, "workspace_id")
