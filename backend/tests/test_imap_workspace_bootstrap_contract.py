import pytest

from services.imap_worker import resolve_unambiguous_workspace_id


class _WorkspaceResolutionSession:
    def __init__(self, *, email_workspaces, runner_workspaces):
        self._results = [list(email_workspaces), list(runner_workspaces)]
        self.calls = 0

    async def scalars(self, _statement):
        result = self._results[self.calls]
        self.calls += 1
        return result


@pytest.mark.asyncio
async def test_first_mailbox_sync_bootstraps_from_registered_workspace():
    session = _WorkspaceResolutionSession(
        email_workspaces=[],
        runner_workspaces=["workspace-registered"],
    )

    workspace_id = await resolve_unambiguous_workspace_id(
        session,
        "user-1",
        "org-1",
    )

    assert workspace_id == "workspace-registered"
    assert session.calls == 2


@pytest.mark.asyncio
async def test_existing_mail_and_registered_workspace_must_not_conflict():
    session = _WorkspaceResolutionSession(
        email_workspaces=["workspace-mail"],
        runner_workspaces=["workspace-registered"],
    )

    workspace_id = await resolve_unambiguous_workspace_id(
        session,
        "user-1",
        "org-1",
    )

    assert workspace_id is None
    assert session.calls == 2


@pytest.mark.asyncio
async def test_existing_mail_scope_remains_authoritative_without_registration():
    session = _WorkspaceResolutionSession(
        email_workspaces=["workspace-mail"],
        runner_workspaces=[],
    )

    workspace_id = await resolve_unambiguous_workspace_id(
        session,
        "user-1",
        "org-1",
    )

    assert workspace_id == "workspace-mail"
    assert session.calls == 2
