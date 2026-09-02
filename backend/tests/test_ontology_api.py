from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from db.models import Email, SenderRelationship
from db.session import get_db
from main import app

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


class MockRow:
    def __init__(
        self,
        sender_email,
        relationship_type,
        confidence_score,
        parent_sender_email=None,
        source_message_id=None,
        source_thread_id=None,
    ):
        self.sender_email = sender_email
        self.relationship_type = relationship_type
        self.confidence_score = confidence_score
        self.parent_sender_email = parent_sender_email
        self.source_message_id = source_message_id
        self.source_thread_id = source_thread_id


class MockResult:
    def __init__(self, items):
        self.items = items

    def scalars(self):
        return self

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None

    def scalar_one_or_none(self):
        return self.items[0] if self.items else None


class MockSession:
    def __init__(self):
        self.items = [
            MockRow(
                "boss@example.com",
                "manager",
                0.95,
                "ceo@example.com",
                "<q2@example.com>",
                "thread-q2",
            )
        ]
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        compiled = str(stmt)
        if "sender_email =" in compiled:
            return MockResult([])
        return MockResult(self.items)

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


class ExistingRelationshipSession(MockSession):
    def __init__(self):
        super().__init__()
        self.items = [MockRow("vendor@example.com", "vendor", 0.5, "buyer@example.com")]

    async def execute(self, stmt):
        return MockResult(self.items)


class CaptureRelationshipSession:
    def __init__(self):
        self.email = Email(
            id=77,
            user_id="owner@example.com",
            organization_id="org-acme",
            message_id="<q2@example.com>",
            thread_id="thread-q2",
            sender="Teammate <teammate@example.com>",
            recipients="owner@example.com",
            subject="Q2 launch",
            date=datetime(2026, 5, 30, tzinfo=timezone.utc),
            body="Let's align the project decision.",
        )
        self.statements = []
        self.added = []
        self.committed = False

    async def execute(self, stmt):
        self.statements.append(stmt)
        if len(self.statements) == 1:
            return MockResult([self.email])
        return MockResult([])

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        pass


async def override_get_db():
    yield MockSession()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Id": "testuser"}) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_relationships(client: TestClient):
    resp = client.get(
        "/api/ontology/relationships",
        params={
            "source_message_id": "<q2@example.com>",
            "source_thread_id": "thread-q2",
        },
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["sender_email"] == "boss@example.com"
    assert items[0]["parent_sender_email"] == "ceo@example.com"
    assert items[0]["source_message_id"] == "<q2@example.com>"
    assert items[0]["source_thread_id"] == "thread-q2"
    assert items[0]["relationship_type"] == "manager"
    assert items[0]["next_action"] == "unavailable"
    assert items[0]["action_reason"] == (
        "No validated relationship action policy is configured."
    )


def test_get_relationships_filters_by_source_and_owner_scope():
    session = MockSession()

    async def override_scoped_get_db():
        yield session

    app.dependency_overrides[get_db] = override_scoped_get_db
    try:
        with TestClient(app, headers={"X-User-Id": "testuser"}) as test_client:
            resp = test_client.get(
                "/api/ontology/relationships",
                params={
                    "source_message_id": "<q2@example.com>",
                    "source_thread_id": "thread-q2",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    query_text = str(session.statements[-1]).lower()
    assert "sender_relationships.user_id" in query_text
    assert "sender_relationships.organization_id" in query_text
    assert "sender_relationships.source_message_id" in query_text
    assert "sender_relationships.source_thread_id" in query_text


def test_create_relationship(client: TestClient):
    resp = client.post(
        "/api/ontology/relationships",
        json={
            "sender_email": "vendor@example.com",
            "parent_sender_email": "buyer@example.com",
            "source_message_id": "<vendor@example.com>",
            "source_thread_id": "thread-vendor",
            "relationship_type": "vendor",
            "confidence_score": 0.8,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sender_email"] == "vendor@example.com"
    assert data["parent_sender_email"] == "buyer@example.com"
    assert data["source_message_id"] == "<vendor@example.com>"
    assert data["source_thread_id"] == "thread-vendor"
    assert data["relationship_type"] == "vendor"
    assert data["next_action"] == "unavailable"
    assert data["action_reason"] == "No validated relationship action policy is configured."


def test_update_relationship_preserves_existing_parent_when_omitted():
    async def override_existing_get_db():
        yield ExistingRelationshipSession()

    app.dependency_overrides[get_db] = override_existing_get_db
    try:
        with TestClient(app, headers={"X-User-Id": "testuser"}) as test_client:
            resp = test_client.post(
                "/api/ontology/relationships",
                json={
                    "sender_email": "vendor@example.com",
                    "relationship_type": "customer",
                    "confidence_score": 0.7,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["sender_email"] == "vendor@example.com"
    assert data["parent_sender_email"] == "buyer@example.com"
    assert data["relationship_type"] == "customer"
    assert data["next_action"] == "unavailable"


def test_capture_relationship_from_source_fails_closed_without_validated_classifier():
    session = CaptureRelationshipSession()

    async def override_capture_get_db():
        yield session

    app.dependency_overrides[get_db] = override_capture_get_db
    try:
        with TestClient(
            app,
            headers={
                "X-User-Id": "owner@example.com",
                "X-Organization-Id": "org-acme",
            },
            raise_server_exceptions=False,
        ) as test_client:
            resp = test_client.post(
                "/api/ontology/relationships/capture-source",
                json={"source_message_id": "<q2@example.com>"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503, resp.text
    assert resp.json() == {
        "detail": (
            "Automatic sender classification is unavailable until validated "
            "relationship evidence is configured."
        )
    }
    assert session.committed is False
    assert session.added == []
    query_text = str(session.statements[0]).lower()
    assert "email_records.user_id" in query_text
    assert "email_records.organization_id" in query_text
    assert "email_records.message_id" in query_text
