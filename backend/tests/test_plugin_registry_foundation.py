"""The first plugin registry slice is durable, scoped, and execution-inert."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.auth import AuthContext, get_auth_context
from db.models import PluginGrant, PluginRegistration
from db.session import get_db
from main import app


class _AsyncSessionAdapter:
    def __init__(self, session: Session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def _registration(uid: str, org: str) -> PluginRegistration:
    return PluginRegistration(
        registration_uid=uid,
        organization_id=org,
        workspace_id=f"workspace-{org}",
        plugin_id="example",
        plugin_version="1.0.0",
        artifact_sha256="a" * 64,
        manifest={"plugin_id": "example"},
    )


def test_registry_persists_grants_and_lists_only_authoritative_tenant_scope():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    PluginRegistration.__table__.create(engine)
    PluginGrant.__table__.create(engine)
    try:
        with Session(engine) as session:
            own = _registration("plugin-own", "org-a")
            other = _registration("plugin-other", "org-b")
            other_workspace = _registration("plugin-other-workspace", "org-a")
            other_workspace.workspace_id = "workspace-other"
            own.grants.append(
                PluginGrant(
                    grant_uid="grant-own",
                    granted_capabilities={"scopes": ["read:calendar"]},
                )
            )
            session.add_all([own, other, other_workspace])
            session.commit()
            assert session.scalar(
                select(PluginGrant).where(PluginGrant.grant_uid == "grant-own")
            )
            assert own.enabled is False

            async def db_override():
                yield _AsyncSessionAdapter(session)

            def auth_override():
                return AuthContext(
                    user_id="admin",
                    role="tenant_admin",
                    organization_id="org-a",
                    group_ids=(),
                    workspace_id="workspace-org-a",
                    session_verifier="override",
                )

            app.dependency_overrides[get_db] = db_override
            app.dependency_overrides[get_auth_context] = auth_override
            try:
                with TestClient(app) as client:
                    response = client.get("/api/plugins")
                    assert response.status_code == 200
                    assert [row["registration_uid"] for row in response.json()] == [
                        "plugin-own"
                    ]
                    assert response.json()[0]["enabled"] is False
                    assert client.post("/api/plugins", json={}).status_code == 405

                    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                        user_id="admin",
                        role="tenant_admin",
                        organization_id="org-a",
                        group_ids=(),
                        workspace_id="workspace-org-a",
                        session_verifier="hmac",
                    )
                    assert client.get("/api/plugins").status_code == 403

                    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                        user_id="member",
                        role="member",
                        organization_id="org-a",
                        group_ids=(),
                        workspace_id="workspace-org-a",
                        session_verifier="override",
                    )
                    assert client.get("/api/plugins").status_code == 403
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_auth_context, None)
    finally:
        engine.dispose()
