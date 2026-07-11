from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from core.config import settings


def _engine_kwargs() -> dict:
    """Engine kwargs shared by the primary and read-only engines.

    Pool sizing values are only passed when configured, so unset settings keep
    SQLAlchemy defaults (and stay compatible with pool classes that do not
    accept sizing, e.g. SQLite's pools in tests). pre_ping validates pooled
    connections at checkout so a restarted/failed-over database does not
    surface as user-facing errors on stale connections; recycle proactively
    replaces connections older than the configured age.
    """
    kwargs: dict = {
        "echo": settings.DEBUG,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    }
    if settings.DB_POOL_SIZE is not None:
        kwargs["pool_size"] = settings.DB_POOL_SIZE
    if settings.DB_MAX_OVERFLOW is not None:
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    if settings.DB_POOL_TIMEOUT_SECONDS is not None:
        kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT_SECONDS
    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs())
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

readonly_database_url = settings.READONLY_DATABASE_URL or settings.DATABASE_URL
readonly_engine = create_async_engine(readonly_database_url, **_engine_kwargs())
AsyncReadOnlySessionLocal = async_sessionmaker(readonly_engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_readonly_db():
    async with AsyncReadOnlySessionLocal() as session:
        yield session
