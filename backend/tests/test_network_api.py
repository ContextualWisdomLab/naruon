import pytest
from fastapi.testclient import TestClient
from main import app
from db.session import get_db
from unittest.mock import patch
from api.network import extract_emails

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")

client = TestClient(app, headers={"X-User-Id": "testuser"})


class MockResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class MockSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, query):
        return MockResult(self.rows)


class QueryCapturingSession(MockSession):
    def __init__(self, rows):
        super().__init__(rows)
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return await super().execute(query)


def get_override(rows):
    async def override_get_db():
        yield MockSession(rows)

    return override_get_db


def test_network_endpoint_exists():
    with patch.dict(
        app.dependency_overrides,
        {
            get_db: get_override(
                [
                    ("alice@example.com", "bob@example.com, charlie@example.com"),
                    ("bob@example.com", "alice@example.com"),
                    ("alice@example.com", "bob@example.com"),
                ]
            )
        },
    ):
        response = client.get("/api/network/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

        nodes = {n["id"] for n in data["nodes"]}
        assert "alice@example.com" in nodes
        assert "bob@example.com" in nodes
        assert "charlie@example.com" in nodes

        edges = {(e["source"], e["target"]): e.get("weight", 1) for e in data["edges"]}
        assert edges[("alice@example.com", "bob@example.com")] == 2
        assert edges[("alice@example.com", "charlie@example.com")] == 1
        assert edges[("bob@example.com", "alice@example.com")] == 1


def test_network_endpoint_returns_stable_node_and_edge_order():
    with patch.dict(
        app.dependency_overrides,
        {
            get_db: get_override(
                [
                    ("zoe@example.com", "amy@example.com"),
                    ("amy@example.com", "zoe@example.com, bob@example.com"),
                ]
            )
        },
    ):
        response = client.get("/api/network/graph")

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [
            {"id": "amy@example.com", "label": "amy@example.com"},
            {"id": "bob@example.com", "label": "bob@example.com"},
            {"id": "zoe@example.com", "label": "zoe@example.com"},
        ],
        "edges": [
            {"source": "amy@example.com", "target": "bob@example.com", "weight": 1},
            {"source": "amy@example.com", "target": "zoe@example.com", "weight": 1},
            {"source": "zoe@example.com", "target": "amy@example.com", "weight": 1},
        ],
    }


def test_network_endpoint_empty_db():
    with patch.dict(app.dependency_overrides, {get_db: get_override([])}):
        response = client.get("/api/network/graph")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 0
        assert len(data["edges"]) == 0


def test_network_endpoint_none_recipients():
    with patch.dict(
        app.dependency_overrides,
        {
            get_db: get_override(
                [
                    ("alice@example.com", None),
                    ("bob@example.com", ""),
                ]
            )
        },
    ):
        response = client.get("/api/network/graph")
        assert response.status_code == 200
        data = response.json()
        nodes = {n["id"] for n in data["nodes"]}
        assert "alice@example.com" in nodes
        assert "bob@example.com" in nodes
        assert len(data["edges"]) == 0


def test_network_endpoint_malformed_emails():
    with patch.dict(
        app.dependency_overrides,
        {
            get_db: get_override(
                [
                    ("not_an_email", "bob@example.com, also_not_an_email"),
                    ("alice@example.com", "malformed@@@example.com"),
                ]
            )
        },
    ):
        response = client.get("/api/network/graph")
        assert response.status_code == 200
        data = response.json()
        nodes = {n["id"] for n in data["nodes"]}
        assert "not_an_email" not in nodes
        assert "also_not_an_email" not in nodes
        assert "malformed@@@example.com" not in nodes

        assert "alice@example.com" in nodes
        assert "bob@example.com" in nodes

        assert len(data["edges"]) == 0


def test_network_endpoint_query_params():
    with patch.dict(
        app.dependency_overrides,
        {
            get_db: get_override(
                [
                    ("alice@example.com", "bob@example.com"),
                ]
            )
        },
    ):
        response = client.get(
            "/api/network/graph?limit=10&user_id=123", headers={"X-User-Id": "123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1


def test_network_graph_query_is_scoped_to_current_user():
    session = QueryCapturingSession([("alice@example.com", "bob@example.com")])

    async def override_get_db():
        yield session

    with patch.dict(app.dependency_overrides, {get_db: override_get_db}):
        response = client.get("/api/network/graph")

    assert response.status_code == 200
    query_text = str(session.queries[-1]).lower()
    assert "email_records.user_id" in query_text
    assert "email_records.organization_id" in query_text

def test_extract_emails_valid():
    assert extract_emails("foo@example.com") == ["foo@example.com"]
    assert extract_emails("User <foo.bar@example.co.uk>") == ["foo.bar@example.co.uk"]
    assert extract_emails("foo+bar@example.com") == ["foo+bar@example.com"]
    assert extract_emails("a@b.com and c@d.org") == ["a@b.com", "c@d.org"]
    assert extract_emails("Mixed case: Foo@Bar.com") == ["Foo@Bar.com"]
    assert extract_emails("123@numbers.com") == ["123@numbers.com"]

def test_extract_emails_invalid():
    assert extract_emails("not_an_email") == []
    assert extract_emails("foo@bar") == []
    assert extract_emails("foo@.com") == []
    assert extract_emails("@domain.com") == []
    assert extract_emails("foo@bar.") == []

def test_extract_emails_empty_or_none():
    assert extract_emails("") == []
    assert extract_emails(None) == []
    assert extract_emails("   ") == []
