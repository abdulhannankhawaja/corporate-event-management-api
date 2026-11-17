"""Tests for signup, login, and protected event endpoints."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.config import settings
from app.security import create_access_token

USER_DATA = {"username": "auth-user", "password": "secure-password-123"}
EVENT_DATA = {
    "title": "Auth Test Event",
    "event_date": "2026-11-20T10:00:00Z",
    "location": "Test Hall",
    "max_capacity": 10,
}


async def test_signup_returns_user_without_password(
    client: AsyncClient,
) -> None:
    """Create a user without returning password information."""
    response = await client.post("/auth/signup", json=USER_DATA)

    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": USER_DATA["username"]}
    assert "password" not in response.text
    assert "hashed_password" not in response.text


async def test_duplicate_signup_returns_conflict(
    client: AsyncClient,
) -> None:
    """Reject signup when the username is already registered."""
    await client.post("/auth/signup", json=USER_DATA)

    response = await client.post("/auth/signup", json=USER_DATA)

    assert response.status_code == 409


async def test_login_returns_bearer_token(
    client: AsyncClient,
) -> None:
    """Authenticate valid credentials using OAuth2 form data."""
    await client.post("/auth/signup", json=USER_DATA)

    response = await client.post("/auth/login", data=USER_DATA)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert "password" not in response.text


async def test_login_rejects_wrong_password(
    client: AsyncClient,
) -> None:
    """Return the common authentication error for incorrect credentials."""
    await client.post("/auth/signup", json=USER_DATA)

    response = await client.post(
        "/auth/login",
        data={**USER_DATA, "password": "wrong-password-123"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
    assert "hashed_password" not in response.text


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("post", EVENT_DATA),
        ("put", {"title": "Updated Event"}),
        ("delete", None),
    ],
)
async def test_event_mutations_require_authentication(
    client: AsyncClient,
    event: dict[str, object],
    method: str,
    body: dict[str, object] | None,
) -> None:
    """Require a bearer token for event creation, update, and deletion."""
    path = "/events" if method == "post" else f"/events/{event['id']}"
    response = await client.request(method, path, json=body)

    assert response.status_code == 401
    assert response.json().get("detail")


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("post", EVENT_DATA),
        ("put", {"title": "Updated Event"}),
        ("delete", None),
    ],
)
async def test_event_mutations_reject_invalid_tokens(
    client: AsyncClient,
    event: dict[str, object],
    method: str,
    body: dict[str, object] | None,
) -> None:
    """Reject invalid bearer tokens on event mutation endpoints."""
    path = "/events" if method == "post" else f"/events/{event['id']}"
    response = await client.request(
        method,
        path,
        json=body,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json().get("detail")


async def test_event_mutations_reject_expired_and_unknown_user_tokens(
    client: AsyncClient,
) -> None:
    """Reject expired tokens and valid tokens for deleted or unknown users."""
    expired_token = jwt.encode(
        {
            "sub": USER_DATA["username"],
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    unknown_user_token = create_access_token("missing-user")

    for token in (expired_token, unknown_user_token):
        response = await client.post(
            "/events",
            json=EVENT_DATA,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


async def test_event_list_is_public(client: AsyncClient) -> None:
    """Allow reading events without an access token."""
    response = await client.get("/events")

    assert response.status_code == 200


async def test_password_is_never_returned(
    client: AsyncClient,
) -> None:
    """Ensure neither plaintext nor hashed password appears in auth responses."""
    signup_response = await client.post("/auth/signup", json=USER_DATA)
    login_response = await client.post("/auth/login", data=USER_DATA)
    wrong_password_response = await client.post(
        "/auth/login",
        data={**USER_DATA, "password": "incorrect-password-123"},
    )

    for response in (
        signup_response,
        login_response,
        wrong_password_response,
    ):
        assert "hashed_password" not in response.text
        assert USER_DATA["password"] not in response.text
