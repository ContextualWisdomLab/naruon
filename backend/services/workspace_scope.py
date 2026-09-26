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
    column("owner_user_id", String()),
    column("created_at", DateTime(timezone=True)),
)


class WorkspaceOrganizationBindingRequired(RuntimeError):
    """Raised when a session lacks trusted workspace ownership evidence."""


class WorkspaceOrganizationConflict(RuntimeError):
    """Raised when a workspace is already bound to a different tenant owner."""


async def _workspace_scope_binding(
    session: AsyncSession,
    workspace_id: str,
) -> tuple[str | None, str | None]:
    """Read organization and personal-user ownership for one opaque workspace."""

    result = await session.execute(
        select(
            _WORKSPACE_REGISTRY.c.organization_id,
            _WORKSPACE_REGISTRY.c.owner_user_id,
        ).where(_WORKSPACE_REGISTRY.c.workspace_id == workspace_id)
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    return row.organization_id, row.owner_user_id


async def _workspace_organization_binding(
    session: AsyncSession,
    workspace_id: str,
) -> str | None:
    """Read the organization binding while preserving the legacy helper contract."""

    organization_id, _owner_user_id = await _workspace_scope_binding(
        session,
        workspace_id,
    )
    return organization_id


async def get_or_create_scoped_workspace(
    session: AsyncSession,
    workspace_id: str,
    organization_id: str | None,
    *,
    owner_user_id: str | None = None,
    session_verifier: SessionVerifier,
) -> Workspace:
    """Return a workspace only after validating server-side tenant ownership.

    Organization scope binds the opaque workspace to ``organization_id`` and
    deliberately does not bind it to one member. Personal scope has
    ``organization_id is None`` and instead requires ``owner_user_id``. OIDC,
    server, and explicit test override identities may establish an entirely
    unbound registry row; HMAC compatibility sessions may consume existing
    evidence but cannot claim ownership. Concurrent claims use insert/CAS
    semantics so only one tenant owner can win.
    """

    if not workspace_id:
        raise WorkspaceOrganizationBindingRequired("workspace claim is required")
    if organization_id is None and not owner_user_id:
        raise WorkspaceOrganizationBindingRequired(
            "personal workspace claims require an authenticated owner user"
        )

    target_organization_id = organization_id
    target_owner_user_id = owner_user_id if organization_id is None else None

    if session_verifier in _TRUSTED_BINDING_VERIFIERS:
        await session.execute(
            insert(_WORKSPACE_REGISTRY)
            .values(
                workspace_id=workspace_id,
                workspace_name=workspace_id,
                organization_id=target_organization_id,
                owner_user_id=target_owner_user_id,
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
                _WORKSPACE_REGISTRY.c.owner_user_id.is_(None),
            )
            .values(
                organization_id=target_organization_id,
                owner_user_id=target_owner_user_id,
            )
        )

    bound_organization_id, bound_owner_user_id = await _workspace_scope_binding(
        session,
        workspace_id,
    )
    if bound_organization_id is None and bound_owner_user_id is None:
        raise WorkspaceOrganizationBindingRequired(
            "workspace has no trusted tenant ownership binding"
        )

    if organization_id is None:
        if bound_organization_id is not None or bound_owner_user_id != owner_user_id:
            raise WorkspaceOrganizationConflict(
                "personal workspace is bound to a different tenant owner"
            )
    elif (
        bound_organization_id != organization_id
        or bound_owner_user_id is not None
    ):
        raise WorkspaceOrganizationConflict(
            "workspace is bound to a different tenant owner"
        )

    result = await session.execute(
        select(Workspace).where(Workspace.workspace_id == workspace_id)
    )
    return result.scalar_one()


async def get_or_create_bound_workspace(
    session: AsyncSession,
    workspace_id: str,
    organization_id: str,
    *,
    session_verifier: SessionVerifier,
) -> Workspace:
    """Compatibility wrapper for organization-scoped workspace ownership."""

    if not organization_id:
        raise WorkspaceOrganizationBindingRequired(
            "workspace and organization claims are required for binding"
        )
    return await get_or_create_scoped_workspace(
        session,
        workspace_id,
        organization_id,
        session_verifier=session_verifier,
    )


async def get_or_create_personal_workspace(
    session: AsyncSession,
    workspace_id: str,
    owner_user_id: str,
    *,
    session_verifier: SessionVerifier,
) -> Workspace:
    """Compatibility-safe entrypoint for a personal opaque workspace binding."""

    return await get_or_create_scoped_workspace(
        session,
        workspace_id,
        None,
        owner_user_id=owner_user_id,
        session_verifier=session_verifier,
    )


async def get_or_create_workspace(
    session: AsyncSession,
    workspace_id: str,
) -> Workspace:
    """Return the ``Workspace`` row for ``workspace_id``, creating it first if needed.

    This compatibility path preserves callers that predate server-side tenant
    binding. It establishes only the workspace foreign-key row and is not
    authorization evidence. New tenant-sensitive callers must use
    :func:`get_or_create_scoped_workspace` (or one of its scoped wrappers) with
    authenticated tenant claims and verifier provenance.
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
