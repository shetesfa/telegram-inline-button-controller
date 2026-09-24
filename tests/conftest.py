"""Pytest fixtures and test environment setup."""

import os
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import config
from app.database import database
from app.database.models import Base

# Configure test environment
os.environ["ADMIN_IDS"] = "12345,67890"
os.environ["BOT_TOKEN"] = "123456789:AAETestSecretToken_XYZ123456"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

config.ADMIN_IDS = {12345, 67890}
config.BOT_TOKEN = "123456789:AAETestSecretToken_XYZ123456"
config.DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Create in-memory SQLite tables before each test and clean up afterwards."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    sm = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    database._engine = engine
    database._sessionmaker = sm

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    database._engine = None
    database._sessionmaker = None
