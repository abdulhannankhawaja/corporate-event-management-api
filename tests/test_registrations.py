"""Tests for event registration endpoints and business rules."""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Registration

REGISTRATION_DATA = {
    "attendee_name": "Aisha Khan",
    "attendee_email": "aisha@example.com",
}


async def register(
    client: AsyncClient,
    event_id: int,
    email: str = "aisha@example.com",
) -> dict[str, object]:
    """Register a standard attendee for an event."""
    response = await client.post(
        f"/events/{event_id}/registrations",
        json={**REGISTRATION_DATA, "attendee_email": email},
    )
    assert response.status_code == 201
    return response.json()


async def test_register_for_event_returns_created_registration(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Create a registration for an existing event."""
    response = await client.post(
        f"/events/{event['id']}/registrations",
        json=REGISTRATION_DATA,
    )

    assert response.status_code == 201
    assert response.json()["event_id"] == event["id"]


async def test_list_event_registrations_returns_created_registration(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """List registrations for an event."""
    registration = await register(client, int(event["id"]))

    response = await client.get(f"/events/{event['id']}/registrations")

    assert response.status_code == 200
    assert response.json()[0]["id"] == registration["id"]


async def test_list_event_registrations_applies_pagination(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Apply skip and limit to an event's registrations."""
    event_id = int(event["id"])
    await register(client, event_id, "first@example.com")
    second = await register(client, event_id, "second@example.com")
    await register(client, event_id, "third@example.com")

    response = await client.get(
        f"/events/{event_id}/registrations",
        params={"skip": 1, "limit": 1},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [second["id"]]


async def test_cancel_registration_returns_no_content(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Cancel a registration and verify it is removed."""
    registration = await register(client, int(event["id"]))

    response = await client.delete(f"/registrations/{registration['id']}")
    listing = await client.get(f"/events/{event['id']}/registrations")

    assert response.status_code == 204
    assert response.content == b""
    assert listing.json() == []


async def test_duplicate_email_is_case_insensitive(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Reject duplicate email addresses regardless of case."""
    await register(client, int(event["id"]), "aisha@example.com")

    response = await client.post(
        f"/events/{event['id']}/registrations",
        json={**REGISTRATION_DATA, "attendee_email": "Aisha@Example.com"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Already registered for this event"}


async def test_full_event_rejects_an_additional_registration(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Reject a new registration after capacity is reached."""
    event_response = await client.post(
        "/events",
        json={
            "title": "Single Seat",
            "event_date": "2026-11-20T10:00:00Z",
            "location": "Small Room",
            "max_capacity": 1,
        },
        headers=auth_headers,
    )
    event_id = event_response.json()["id"]
    await register(client, event_id, "first@example.com")

    response = await client.post(
        f"/events/{event_id}/registrations",
        json={**REGISTRATION_DATA, "attendee_email": "second@example.com"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Event is full"}


async def test_registration_for_missing_event_returns_not_found(
    client: AsyncClient,
) -> None:
    """Return 404 when an event does not exist."""
    response = await client.post(
        "/events/9999/registrations",
        json=REGISTRATION_DATA,
    )

    assert response.status_code == 404


async def test_registration_rejects_invalid_email(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Reject malformed attendee email addresses."""
    response = await client.post(
        f"/events/{event['id']}/registrations",
        json={**REGISTRATION_DATA, "attendee_email": "invalid-email"},
    )

    assert response.status_code == 422


async def test_cancel_missing_registration_returns_not_found(
    client: AsyncClient,
) -> None:
    """Return 404 when a registration does not exist."""
    response = await client.delete("/registrations/9999")

    assert response.status_code == 404


async def test_capacity_cannot_be_lowered_below_registration_count(
    client: AsyncClient,
    event: dict[str, object],
    auth_headers: dict[str, str],
) -> None:
    """Reject capacity updates below the number already registered."""
    await register(client, int(event["id"]))

    response = await client.put(
        f"/events/{event['id']}",
        json={"max_capacity": 2},
        headers=auth_headers,
    )

    assert response.status_code == 200
    await register(client, int(event["id"]), "second@example.com")
    conflict_response = await client.put(
        f"/events/{event['id']}",
        json={"max_capacity": 1},
        headers=auth_headers,
    )

    assert conflict_response.status_code == 409


async def test_deleting_event_removes_its_registrations(
    client: AsyncClient,
    event: dict[str, object],
    auth_headers: dict[str, str],
    database_session: AsyncSession,
) -> None:
    """Delete an event and confirm its registrations are removed."""
    event_id = int(event["id"])
    await register(client, event_id)

    response = await client.delete(
        f"/events/{event_id}",
        headers=auth_headers,
    )
    remaining = await database_session.scalar(
        select(func.count())
        .select_from(Registration)
        .where(Registration.event_id == event_id)
    )

    assert response.status_code == 204
    assert remaining == 0
