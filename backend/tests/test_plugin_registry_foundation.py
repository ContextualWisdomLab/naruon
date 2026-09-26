"""The first plugin registry slice is durable, scoped, and execution-inert."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.auth import AuthContext, get_auth_context
from db.models import (
    PluginArtifact,
    PluginDefinition,
    PluginGrant,
    PluginRegistration,
    PluginRelease,
)
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
    )


def test_registry_persists_grants_and_lists_only_authoritative_tenant_scope():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (
        PluginDefinition,
        PluginRelease,
        PluginArtifact,
        PluginRegistration,
        PluginGrant,
    ):
        model.__table__.create(engine)
    try:
        with Session(engine) as session:
            definition = PluginDefinition(
                plugin_uid="plugin-definition",
                plugin_id="example",
                display_name="Example",
            )
            release = PluginRelease(
                release_uid="plugin-release",
                plugin_version="1.0.0",
                publisher_id="publisher",
                manifest={"plugin_id": "example"},
            )
            artifact = PluginArtifact(
                artifact_uid="plugin-artifact",
                artifact_sha256="a" * 64,
                distribution_uri="https://example.test/plugin.tar.gz",
                source_commit="b" * 40,
            )
            other_release = PluginRelease(
                release_uid="plugin-other-release",
                plugin_version="2.0.0",
                publisher_id="publisher",
                manifest={"plugin_id": "example"},
            )
            other_artifact = PluginArtifact(
                artifact_uid="plugin-other-artifact",
                artifact_sha256="c" * 64,
                distribution_uri="https://example.test/plugin-v2.tar.gz",
                source_commit="d" * 40,
            )
            definition.releases.append(release)
            definition.releases.append(other_release)
            release.artifacts.append(artifact)
            other_release.artifacts.append(other_artifact)
            own = _registration("plugin-own", "org-a")
            other = _registration("plugin-other", "org-b")
            other_workspace = _registration("plugin-other-workspace", "org-a")
            other_workspace.workspace_id = "workspace-other"
            artifact.registrations.extend([own, other_workspace])
            other_artifact.registrations.append(other)
            own.grants.append(
                PluginGrant(
                    grant_uid="grant-own",
                    granted_capabilities={"scopes": ["read:calendar"]},
                )
            )
            session.add(definition)
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
                    assert response.json()[0]["plugin_id"] == "example"
                    assert response.json()[0]["plugin_version"] == "1.0.0"
                    assert response.json()[0]["artifact_sha256"] == "a" * 64
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
