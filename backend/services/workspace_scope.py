import datetime
from typing import Literal

from sqlalchemy import DateTime, String, column, select, table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Workspace

SessionVerifier = Literal["hmac", "oidc", "override", "server"]
_TRUSTED_BINDING_VERIFIERS = frozenset({"oidc", "override", "server"})
_WORKSPACE_REGISTRY = table(
    "workspace_entities",
    column("workspace_id", String()),
    column("workspace_name", String()),
    column("organization_id", String()),
    column("created_at", DateTime(timezone=True)),
)


class WorkspaceOrganizationBindingRequired(RuntimeError):
    """Raised when a session cannot establish an unbound workspace owner."""


class WorkspaceOrganizationConflict(RuntimeError):
    """Raised when a workspace is already bound to another organization."""


async def _workspace_organization_binding(
    session: AsyncSession,
    workspace_id: str,
) -> str | None:
    """Read the server-side organization binding for one opaque workspace."""

    result = await session.execute(
        select(_WORKSPACE_REGISTRY.c.organization_id).where(
            _WORKSPACE_REGISTRY.c.workspace_id == workspace_id
        )
    )
    row = result.one_or_none()
    return None if row is None else row.organization_id


async def get_or_create_bound_workspace(
    session: AsyncSession,
    workspace_id: str,
    organization_id: str,
    *,
    session_verifier: SessionVerifier,
) -> Workspace:
    """Return a workspace only after validating its server-side organization binding.

    OIDC and explicit server/test override identities may establish a missing
    binding because those paths are the configured membership-authority boundary.
    HMAC compatibility sessions may use an already-bound workspace but can never
    create or claim a binding. Concurrent bind attempts use insert/CAS semantics;
    the losing organization observes the winner and fails closed.
    """

    if not workspace_id or not organization_id:
        raise WorkspaceOrganizationBindingRequired(
            "workspace and organization claims are required for binding"
        )

    if session_verifier in _TRUSTED_BINDING_VERIFIERS:
        await session.execute(
            insert(_WORKSPACE_REGISTRY)
            .values(
                workspace_id=workspace_id,
                workspace_name=workspace_id,
                organization_id=organization_id,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            .on_conflict_do_nothing(
                index_elements=[_WORKSPACE_REGISTRY.c.workspace_id]
            )
        )
        await session.execute(
            update(_WORKSPACE_REGISTRY)
            .where(
                _WORKSPACE_REGISTRY.c.workspace_id == workspace_id,
                _WORKSPACE_REGISTRY.c.organization_id.is_(None),
            )
            .values(organization_id=organization_id)
        )

    bound_organization_id = await _workspace_organization_binding(
        session,
        workspace_id,
    )
    if bound_organization_id is None:
        raise WorkspaceOrganizationBindingRequired(
            "workspace has no trusted organization binding"
        )
    if bound_organization_id != organization_id:
        raise WorkspaceOrganizationConflict(
            "workspace is bound to a different organization"
        )

    result = await session.execute(
        select(Workspace).where(Workspace.workspace_id == workspace_id)
    )
    return result.scalar_one()


async def get_or_create_workspace(
    session: AsyncSession,
    workspace_id: str,
) -> Workspace:
    """Return the ``Workspace`` row for ``workspace_id``, creating it first if needed.

    This compatibility path preserves callers that predate server-side
    workspace↔organization binding. It establishes only the workspace foreign-key
    row and is not authorization evidence. New tenant-sensitive callers must use
    :func:`get_or_create_bound_workspace` with an authenticated organization and
    verifier.
    """

    result = await session.execute(
        insert(Workspace)
        .values(
            workspace_id=workspace_id,
            workspace_name=workspace_id,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=[Workspace.workspace_id])
        .returning(Workspace)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        result = await session.execute(
            select(Workspace).where(Workspace.workspace_id == workspace_id)
        )
        workspace = result.scalar_one()
    return workspace
