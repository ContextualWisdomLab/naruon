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


def _settings_namespace(**overrides) -> SimpleNamespace:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://primary/db",
        "READONLY_DATABASE_URL": None,
        "DEBUG": False,
        "DB_POOL_SIZE": None,
        "DB_MAX_OVERFLOW": None,
        "DB_POOL_TIMEOUT_SECONDS": None,
        "DB_POOL_RECYCLE_SECONDS": 1800,
        "DB_POOL_PRE_PING": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_fakes(monkeypatch, created: list[tuple[str, dict]]):
    def fake_create_async_engine(url, **kwargs):
        created.append((url, kwargs))
        return SimpleNamespace(url=url, kwargs=kwargs)

    def fake_sessionmaker(engine, *, expire_on_commit=False):
        return SimpleNamespace(engine=engine, expire_on_commit=expire_on_commit)

    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine
    )
    monkeypatch.setattr("sqlalchemy.ext.asyncio.async_sessionmaker", fake_sessionmaker)


def test_readonly_session_uses_replica_url_when_configured(monkeypatch):
    created: list[tuple[str, dict]] = []
    _install_fakes(monkeypatch, created)

    import core.config as config

    monkeypatch.setattr(
        config,
        "settings",
        _settings_namespace(
            READONLY_DATABASE_URL="postgresql+asyncpg://replica/db",
        ),
    )

    reloaded = _import_isolated_db_session()

    assert [url for url, _kwargs in created] == [
        "postgresql+asyncpg://primary/db",
        "postgresql+asyncpg://replica/db",
    ]
    assert reloaded.AsyncReadOnlySessionLocal.engine.url == "postgresql+asyncpg://replica/db"


def test_readonly_session_falls_back_to_primary_url_without_replica(monkeypatch):
    created: list[tuple[str, dict]] = []
    _install_fakes(monkeypatch, created)

    import core.config as config

    monkeypatch.setattr(config, "settings", _settings_namespace())

    reloaded = _import_isolated_db_session()

    assert [url for url, _kwargs in created] == [
        "postgresql+asyncpg://primary/db",
        "postgresql+asyncpg://primary/db",
    ]
    assert reloaded.AsyncReadOnlySessionLocal.engine.url == "postgresql+asyncpg://primary/db"
    assert hasattr(reloaded, "get_readonly_db")


def test_engines_enable_pre_ping_and_recycle_by_default(monkeypatch):
    created: list[tuple[str, dict]] = []
    _install_fakes(monkeypatch, created)

    import core.config as config

    monkeypatch.setattr(config, "settings", _settings_namespace())

    _import_isolated_db_session()

    for _url, kwargs in created:
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 1800
        # Sizing left unset -> SQLAlchemy defaults, SQLite-compatible.
        assert "pool_size" not in kwargs
        assert "max_overflow" not in kwargs
        assert "pool_timeout" not in kwargs


def test_engines_apply_configured_pool_sizing(monkeypatch):
    created: list[tuple[str, dict]] = []
    _install_fakes(monkeypatch, created)

    import core.config as config

    monkeypatch.setattr(
        config,
        "settings",
        _settings_namespace(
            DB_POOL_SIZE=20,
            DB_MAX_OVERFLOW=10,
            DB_POOL_TIMEOUT_SECONDS=5,
            DB_POOL_RECYCLE_SECONDS=900,
            DB_POOL_PRE_PING=False,
        ),
    )

    _import_isolated_db_session()

    for _url, kwargs in created:
        assert kwargs["pool_size"] == 20
        assert kwargs["max_overflow"] == 10
        assert kwargs["pool_timeout"] == 5
        assert kwargs["pool_recycle"] == 900
        assert kwargs["pool_pre_ping"] is False
