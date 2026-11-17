"""Shared fixtures for API tests."""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Importing models ensures test metadata includes every table.
from app import models  # noqa: F401
from app.db import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Create an isolated in-memory SQLite database for a test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        """Yield a session connected to this test's SQLite database."""
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield engine
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """Yield an async HTTP client connected to the application."""
    del test_engine
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Create and log in a user, returning bearer authorization headers."""
    user_data = {"username": "testuser", "password": "test-password-123"}
    signup_response = await client.post("/auth/signup", json=user_data)
    assert signup_response.status_code == 201
    login_response = await client.post(
        "/auth/login",
        data=user_data,
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def event(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> dict[str, object]:
    """Create a standard event through the authenticated API."""
    response = await client.post(
        "/events",
        json={
            "title": "Python Summit",
            "description": "A test event.",
            "event_date": "2026-11-20T10:00:00Z",
            "location": "Main Hall",
            "max_capacity": 10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def database_session(
    test_engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    """Yield a session for checking persisted test database state."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
