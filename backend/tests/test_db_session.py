import importlib
import sys
from types import SimpleNamespace


def _import_isolated_db_session():
    original = sys.modules.get("db.session")
    sys.modules.pop("db.session", None)
    try:
        return importlib.import_module("db.session")
    finally:
        if original is None:
            sys.modules.pop("db.session", None)
        else:
            sys.modules["db.session"] = original


def test_readonly_session_uses_replica_url_when_configured(monkeypatch):
    created_urls: list[str] = []

    def fake_create_async_engine(url, *, echo=False):
        created_urls.append(url)
        return SimpleNamespace(url=url, echo=echo)

    def fake_sessionmaker(engine, *, expire_on_commit=False):
        return SimpleNamespace(engine=engine, expire_on_commit=expire_on_commit)

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine)
    monkeypatch.setattr("sqlalchemy.ext.asyncio.async_sessionmaker", fake_sessionmaker)

    import core.config as config

    monkeypatch.setattr(
        config,
        "settings",
        SimpleNamespace(
            DATABASE_URL="postgresql+asyncpg://primary/db",
            READONLY_DATABASE_URL="postgresql+asyncpg://replica/db",
            DEBUG=False,
        ),
    )

    reloaded = _import_isolated_db_session()

    assert created_urls == [
        "postgresql+asyncpg://primary/db",
        "postgresql+asyncpg://replica/db",
    ]
    assert reloaded.AsyncReadOnlySessionLocal.engine.url == "postgresql+asyncpg://replica/db"


def test_readonly_session_falls_back_to_primary_url_without_replica(monkeypatch):
    created_urls: list[str] = []

    def fake_create_async_engine(url, *, echo=False):
        created_urls.append(url)
        return SimpleNamespace(url=url, echo=echo)

    def fake_sessionmaker(engine, *, expire_on_commit=False):
        return SimpleNamespace(engine=engine, expire_on_commit=expire_on_commit)

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine)
    monkeypatch.setattr("sqlalchemy.ext.asyncio.async_sessionmaker", fake_sessionmaker)

    import core.config as config

    monkeypatch.setattr(
        config,
        "settings",
        SimpleNamespace(
            DATABASE_URL="postgresql+asyncpg://primary/db",
            READONLY_DATABASE_URL=None,
            DEBUG=False,
        ),
    )

    reloaded = _import_isolated_db_session()

    assert created_urls == [
        "postgresql+asyncpg://primary/db",
        "postgresql+asyncpg://primary/db",
    ]
    assert reloaded.AsyncReadOnlySessionLocal.engine.url == "postgresql+asyncpg://primary/db"
    assert hasattr(reloaded, "get_readonly_db")
