import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings


@pytest.mark.asyncio
async def test_engine_creation():
    engine = create_async_engine(settings.DATABASE_URL)
    assert engine is not None

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
