from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

readonly_database_url = settings.READONLY_DATABASE_URL or settings.DATABASE_URL
readonly_engine = create_async_engine(readonly_database_url, echo=settings.DEBUG)
AsyncReadOnlySessionLocal = async_sessionmaker(readonly_engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_readonly_db():
    async with AsyncReadOnlySessionLocal() as session:
        yield session
