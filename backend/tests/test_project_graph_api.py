import datetime
import uuid

import httpx
import pytest
import pytest_asyncio
from asyncpg.exceptions import (
    InvalidAuthorizationSpecificationError,
    InvalidPasswordError,
)
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.projects as projects_api
from db.models import (
    Base,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
)
from db.session import get_db
from main import app
from services.project_graph import (
    ProjectCandidateSummary,
    ProjectCitation,
    ProjectCorrection,
    ProjectSourceSegment,
    extract_project_semantics,
    persist_project_graph_projection,
)
from core.config import settings


@pytest.mark.asyncio
async def test_project_candidates_endpoint_maps_scope_without_database(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    captured = {}
    observed_at = datetime.datetime.now(datetime.timezone.utc)

    async def fake_list_project_candidates(session, *, scope, limit):
        captured["scope"] = scope
        captured["limit"] = limit
        return (
            ProjectCandidateSummary(
                candidate_uid="project_candidate:test",
                project_uid="project_candidate:test",
                title="Project: API contract",
                status_code="candidate",
                score=0.91,
                object_count=3,
                requirement_count=1,
                issue_count=1,
                milestone_count=0,
                deliverable_count=1,
                participant_count=0,
                source_segment_count=1,
                representative_object_uids=("requirement:test",),
                citation_bundle=(
                    ProjectCitation(
                        content_segment_uid="seg-test",
                        source_kind="email_body",
                        source_record_uid="<api@example.com>",
                        heading_path="Requirements",
                        segment_path="/document[1]/paragraph[1]",
                        ordinal_index=1,
                        safe_text_excerpt="요구사항 근거 문단",
                    ),
                ),
                updated_at=observed_at,
            ),
        )

    async def override_get_db():
        yield object()

    monkeypatch.setattr(
        projects_api,
        "list_project_candidates",
        fake_list_project_candidates,
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(
            user_id="reviewer",
            organization_id="org-acme",
            role="organization_admin",
        ) as client:
            response = await client.get("/api/projects/candidates?limit=5")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["limit"] == 5
    assert captured["scope"].can_read_organization_scope is True
    candidate = response.json()["candidates"][0]
    assert candidate["candidate_uid"] == "project_candidate:test"
    assert candidate["citation_bundle"][0]["safe_text_excerpt"] == "요구사항 근거 문단"


@pytest.mark.asyncio
async def test_project_correction_endpoint_commits_and_returns_audit_trail(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    captured = {}
    observed_at = datetime.datetime.now(datetime.timezone.utc)

    class DummySession:
        committed = False

        async def commit(self):
            self.committed = True

    dummy_session = DummySession()

    async def fake_apply_project_correction(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return ProjectCorrection(
            correction_uid="project_correction_test",
            object_uid=kwargs["object_uid"],
            correction_action=kwargs["correction_action"],
            before_json={"status_code": "candidate"},
            after_json=kwargs["after_json"],
            rationale=kwargs["rationale"],
            actor_user_id=kwargs["actor_user_id"],
            source_segment_uids=("seg-test",),
            created_at=observed_at,
        )

    async def override_get_db():
        yield dummy_session

    monkeypatch.setattr(
        projects_api,
        "apply_project_correction",
        fake_apply_project_correction,
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(
            user_id="reviewer",
            organization_id="org-acme",
        ) as client:
            response = await client.post(
                "/api/projects/project_candidate:test/corrections",
                json={
                    "object_uid": "requirement:test",
                    "correction_action": "confirm_requirement",
                    "after_json": {"status_code": "approved"},
                    "rationale": "reviewed",
                    "source_segment_uids": ["seg-test"],
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert dummy_session.committed is True
    assert captured["actor_user_id"] == "reviewer"
    assert captured["project_uid"] == "project_candidate:test"
    assert captured["source_segment_uids"] == ("seg-test",)
    body = response.json()
    assert body["before_json"]["status_code"] == "candidate"
    assert body["after_json"]["status_code"] == "approved"


@pytest_asyncio.fixture(scope="function")
async def project_graph_api_sessionmaker():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    except (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
        OperationalError,
        OSError,
    ) as exc:
        pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
    finally:
        await engine.dispose()


@pytest.fixture
def project_graph_api_db_override(project_graph_api_sessionmaker):
    async def override_get_db():
        async with project_graph_api_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_project_graph_api_exposes_candidates_traceability_and_corrections(
    dev_auth_dependency_overrides,
    project_graph_api_db_override,
    project_graph_api_sessionmaker,
):
    user_id = f"project-api-user-{uuid.uuid4().hex}"
    organization_id = "org-acme"
    async with project_graph_api_sessionmaker() as session:
        await _seed_projection(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )

    async with _client(user_id=user_id, organization_id=organization_id) as client:
        candidates_response = await client.get("/api/projects/candidates")
        assert candidates_response.status_code == 200
        candidates = candidates_response.json()["candidates"]
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["candidate_uid"].startswith("project_candidate:")
        assert candidate["source_segment_count"] == 1
        assert candidate["requirement_count"] == 1
        assert candidate["issue_count"] == 1
        assert candidate["milestone_count"] == 1
        assert candidate["deliverable_count"] == 1
        assert candidate["citation_bundle"][0]["segment_path"] == (
            "/document[1]/paragraph[1]"
        )

        confirm_response = await client.post(
            f"/api/projects/candidates/{candidate['candidate_uid']}/confirm"
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status_code"] == "confirmed"

        trace_response = await client.get(
            f"/api/projects/{candidate['project_uid']}/traceability"
        )
        assert trace_response.status_code == 200
        traceability = trace_response.json()
        assert traceability["project_uid"] == candidate["project_uid"]
        assert len(traceability["objects"]) >= 6
        assert all(item["citation_bundle"] for item in traceability["objects"])
        assert any(
            edge["edge_type"] == "segment_evidences_project_object"
            for edge in traceability["edges"]
        )

        requirement = next(
            item
            for item in traceability["objects"]
            if item["object_type"] == "requirement"
        )
        evidence_response = await client.get(
            f"/api/projects/{candidate['project_uid']}"
            f"/evidence/{requirement['object_uid']}"
        )
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["object_uid"] == requirement["object_uid"]
        assert "결제 화면" in evidence["citation_bundle"][0]["safe_text_excerpt"]

        correction_response = await client.post(
            f"/api/projects/{candidate['project_uid']}/corrections",
            json={
                "object_uid": requirement["object_uid"],
                "correction_action": "confirm_requirement",
                "after_json": {
                    "status_code": "approved",
                    "title": "Requirement: approved checkout retry guidance",
                },
                "rationale": "Reviewed with cited source paragraph.",
            },
        )
        assert correction_response.status_code == 200
        correction = correction_response.json()
        assert correction["before_json"]["status_code"] == "confirmed"
        assert correction["after_json"]["status_code"] == "approved"
        assert correction["source_segment_uids"] == [
            evidence["citation_bundle"][0]["content_segment_uid"]
        ]

        updated_evidence_response = await client.get(
            f"/api/projects/{candidate['project_uid']}"
            f"/evidence/{requirement['object_uid']}"
        )
        assert updated_evidence_response.status_code == 200
        assert updated_evidence_response.json()["status_code"] == "approved"


@pytest.mark.asyncio
async def test_project_graph_api_enforces_member_scope_and_allows_org_admin(
    dev_auth_dependency_overrides,
    project_graph_api_db_override,
    project_graph_api_sessionmaker,
):
    owner_id = f"project-api-owner-{uuid.uuid4().hex}"
    other_user_id = f"project-api-other-{uuid.uuid4().hex}"
    organization_id = "org-acme"
    async with project_graph_api_sessionmaker() as session:
        await _seed_projection(
            session,
            user_id=owner_id,
            organization_id=organization_id,
        )

    async with _client(
        user_id=other_user_id,
        organization_id=organization_id,
    ) as client:
        response = await client.get("/api/projects/candidates")
        assert response.status_code == 200
        assert response.json()["candidates"] == []

    async with _client(
        user_id=other_user_id,
        organization_id=organization_id,
        role="organization_admin",
    ) as client:
        response = await client.get("/api/projects/candidates")
        assert response.status_code == 200
        candidates = response.json()["candidates"]
        assert len(candidates) == 1
        assert candidates[0]["source_segment_count"] == 1


@pytest.mark.asyncio
async def test_project_graph_api_returns_404_when_evidence_segment_is_stale(
    dev_auth_dependency_overrides,
    project_graph_api_db_override,
    project_graph_api_sessionmaker,
):
    user_id = f"project-api-stale-{uuid.uuid4().hex}"
    organization_id = "org-acme"
    async with project_graph_api_sessionmaker() as session:
        seeded = await _seed_projection(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        project_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_type == "requirement",
                ProjectGraphObjectRecord.user_id == user_id,
            )
        )
        assert project_object is not None
        project_object.source_segment_uids = ["missing-segment"]
        await session.commit()

    async with _client(user_id=user_id, organization_id=organization_id) as client:
        response = await client.get(
            f"/api/projects/{seeded['candidate_uid']}"
            f"/evidence/{project_object.object_uid}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Project graph source evidence not found"


async def _seed_projection(
    session,
    *,
    user_id: str,
    organization_id: str,
) -> dict[str, str]:
    await _cleanup_user(session, user_id)
    segment = await _seed_source_segment(
        session,
        user_id=user_id,
        organization_id=organization_id,
    )
    extraction = extract_project_semantics([_source_segment(segment)])
    result = await persist_project_graph_projection(
        session,
        extraction=extraction,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=f"workspace-{organization_id}",
    )
    await session.commit()
    candidate = next(
        record
        for record in result.objects
        if record.object_type == "project_candidate"
    )
    return {
        "candidate_uid": candidate.object_uid,
        "segment_uid": segment.content_segment_uid,
    }


async def _seed_source_segment(
    session,
    *,
    user_id: str,
    organization_id: str,
) -> ContentSegmentRecord:
    now = datetime.datetime.now(datetime.timezone.utc)
    email = Email(
        user_id=user_id,
        organization_id=organization_id,
        message_id=f"<{uuid.uuid4().hex}@example.com>",
        thread_id=f"thread-{uuid.uuid4().hex}",
        fingerprint=f"sha256:{uuid.uuid4().hex}",
        sender="partner@example.com",
        recipients="owner@example.com",
        subject="Project Alpha checkout launch",
        date=now,
        body="요구사항 본문",
    )
    session.add(email)
    await session.flush()
    node = ContentNodeRecord(
        content_node_uid=f"node-{uuid.uuid4().hex[:16]}",
        email_id=email.id,
        attachment_id=None,
        source_kind="email_body",
        source_record_uid=email.message_id,
        parent_node_uid=None,
        node_kind="document",
        node_path="/document[1]",
        ordinal_index=1,
        display_label="body",
        safe_text_content="프로젝트 요구사항 문단",
        content_hash=uuid.uuid4().hex,
        created_at=now,
    )
    session.add(node)
    await session.flush()
    segment = ContentSegmentRecord(
        content_segment_uid=f"seg-{uuid.uuid4().hex[:16]}",
        email_id=email.id,
        attachment_id=None,
        content_node_id=node.content_node_id,
        source_kind="email_body",
        source_record_uid=email.message_id,
        segment_kind="paragraph",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=1,
        heading_path="Project kickoff",
        safe_text_content=(
            "프로젝트 Alpha launch 요구사항: 결제 화면은 카드 승인 실패 시 "
            "재시도 안내를 반드시 보여줘야 합니다. 2026-08-01 일정까지 "
            "SRS 산출물과 담당자 PM을 확정하고 blocker 리스크를 해결합니다."
        ),
        content_hash=uuid.uuid4().hex,
        word_count=25,
        created_at=now,
    )
    session.add(segment)
    await session.flush()
    return segment


def _source_segment(segment: ContentSegmentRecord) -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid=segment.content_segment_uid,
        source_kind=segment.source_kind,
        source_record_uid=segment.source_record_uid,
        safe_text_content=segment.safe_text_content,
        heading_path=segment.heading_path,
        segment_path=segment.segment_path,
        ordinal_index=segment.ordinal_index,
    )


async def _cleanup_user(session, user_id: str) -> None:
    await session.execute(
        delete(ProjectGraphCorrectionRecord).where(
            ProjectGraphCorrectionRecord.user_id == user_id
        )
    )
    await session.execute(
        delete(ProjectGraphEdgeRecord).where(ProjectGraphEdgeRecord.user_id == user_id)
    )
    await session.execute(
        delete(ProjectGraphObjectRecord).where(
            ProjectGraphObjectRecord.user_id == user_id
        )
    )
    await session.execute(delete(Email).where(Email.user_id == user_id))
    await session.flush()


def _client(
    *,
    user_id: str,
    organization_id: str,
    role: str = "member",
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={
            "X-User-Id": user_id,
            "X-Organization-Id": organization_id,
            "X-User-Role": role,
        },
    )
