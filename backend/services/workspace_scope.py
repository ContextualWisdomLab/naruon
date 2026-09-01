from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Workspace


async def get_or_create_workspace(
    session: AsyncSession,
    workspace_id: str,
) -> Workspace:
    """Return the ``Workspace`` row for ``workspace_id``, creating it first if needed.

    ``workspace_id`` is the signed session's ``workspace`` claim
    (``workspace-<organization_id>`` or ``workspace-<user_id>`` for
    personal scope, per ``api/auth.py``/``_derive_workspace_id``), not the
    model's own opaque default. Rows created here always use that claim as
    the primary key so ``Document.workspace_id``'s foreign key resolves.
    """
    result = await session.execute(
        select(Workspace).where(Workspace.workspace_id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        workspace = Workspace(workspace_id=workspace_id, workspace_name=workspace_id)
        session.add(workspace)
        await session.flush()
    return workspace
