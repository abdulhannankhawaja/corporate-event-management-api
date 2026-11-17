"""Tests for event endpoints and request validation."""

import pytest
from httpx import AsyncClient

EVENT_DATA = {
    "title": "Python Summit",
    "description": "A test event.",
    "event_date": "2026-11-20T10:00:00Z",
    "location": "Main Hall",
    "max_capacity": 10,
}


async def create_event(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str,
    event_date: str,
) -> dict[str, object]:
    """Create an event with a given title and date."""
    response = await client.post(
        "/events",
        json={**EVENT_DATA, "title": title, "event_date": event_date},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def test_create_event_returns_created_resource(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Create an event and return its representation."""
    response = await client.post(
        "/events",
        json=EVENT_DATA,
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Python Summit"


async def test_list_events_returns_created_event(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """List events created in the current test."""
    response = await client.get("/events")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [event["id"]]


async def test_get_event_returns_matching_event(
    client: AsyncClient,
    event: dict[str, object],
) -> None:
    """Retrieve an event by identifier."""
    response = await client.get(f"/events/{event['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == event["id"]


async def test_update_event_changes_provided_fields(
    client: AsyncClient,
    event: dict[str, object],
    auth_headers: dict[str, str],
) -> None:
    """Update an event without replacing omitted fields."""
    response = await client.put(
        f"/events/{event['id']}",
        json={"location": "Updated Hall"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["location"] == "Updated Hall"
    assert response.json()["title"] == event["title"]


@pytest.mark.parametrize("field", ["title", "event_date", "location", "max_capacity"])
async def test_update_event_rejects_null_non_nullable_fields(
    client: AsyncClient,
    event: dict[str, object],
    auth_headers: dict[str, str],
    field: str,
) -> None:
    """Reject explicit nulls for event fields that cannot be null."""
    response = await client.put(
        f"/events/{event['id']}",
        json={field: None},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert f"body.{field}" in response.json()["detail"]


async def test_delete_event_then_get_returns_not_found(
    client: AsyncClient,
    event: dict[str, object],
    auth_headers: dict[str, str],
) -> None:
    """Delete an event and verify it is no longer available."""
    delete_response = await client.delete(
        f"/events/{event['id']}",
        headers=auth_headers,
    )
    get_response = await client.get(f"/events/{event['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404


async def test_get_missing_event_returns_not_found(
    client: AsyncClient,
) -> None:
    """Return 404 for an unknown event identifier."""
    response = await client.get("/events/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {**EVENT_DATA, "title": ""},
        {**EVENT_DATA, "title": "   "},
        {**EVENT_DATA, "max_capacity": 0},
        {**EVENT_DATA, "max_capacity": -5},
        {"title": "Missing fields"},
        {**EVENT_DATA, "event_date": "not-a-date"},
    ],
)
async def test_create_event_rejects_invalid_payloads(
    client: AsyncClient,
    auth_headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    """Reject blank, invalid, or incomplete event data."""
    response = await client.post(
        "/events",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_create_event_accepts_timezone_aware_datetime(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Accept an aware date and return normalized naive UTC."""
    response = await client.post(
        "/events",
        json=EVENT_DATA,
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["event_date"] == "2026-11-20T10:00:00"


async def test_event_pagination_applies_limit_and_skip(
    client: AsyncClient,
    auth_headers: dict[str, str],
    event: dict[str, object],
) -> None:
    """Apply limit and offset to the ordered event list."""
    await create_event(
        client,
        auth_headers,
        title="Second Event",
        event_date="2026-11-21T10:00:00Z",
    )
    await create_event(
        client,
        auth_headers,
        title="Third Event",
        event_date="2026-11-22T10:00:00Z",
    )

    limited = await client.get("/events?limit=2")
    skipped = await client.get("/events?skip=2&limit=2")

    assert limited.status_code == 200
    assert len(limited.json()) == 2
    assert skipped.status_code == 200
    assert [item["title"] for item in skipped.json()] == ["Third Event"]
    assert limited.json()[0]["id"] == event["id"]


@pytest.mark.parametrize("query", ["limit=0", "limit=1000", "skip=-1"])
async def test_event_pagination_rejects_invalid_bounds(
    client: AsyncClient,
    query: str,
) -> None:
    """Reject pagination values outside configured bounds."""
    response = await client.get(f"/events?{query}")

    assert response.status_code == 422


async def test_event_title_filter_is_case_insensitive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    event: dict[str, object],
) -> None:
    """Match titles partially without regard to case."""
    await create_event(
        client,
        auth_headers,
        title="Python Workshop",
        event_date="2026-11-20T12:00:00Z",
    )
    await create_event(
        client,
        auth_headers,
        title="JavaScript Meetup",
        event_date="2026-11-20T14:00:00Z",
    )

    response = await client.get("/events?title=pYtHoN")

    assert response.status_code == 200
    assert {item["title"] for item in response.json()} == {
        event["title"],
        "Python Workshop",
    }


async def test_event_date_filter_matches_calendar_day(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Match events within the requested calendar-day range."""
    await create_event(
        client,
        auth_headers,
        title="Same Day Early",
        event_date="2026-11-20T00:00:00Z",
    )
    await create_event(
        client,
        auth_headers,
        title="Same Day Late",
        event_date="2026-11-20T23:59:59Z",
    )
    await create_event(
        client,
        auth_headers,
        title="Next Day",
        event_date="2026-11-21T00:00:00Z",
    )

    response = await client.get("/events?date=2026-11-20")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == [
        "Same Day Early",
        "Same Day Late",
    ]


async def test_event_filters_combine_with_each_other(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Combine title and date filters in a single event query."""
    await create_event(
        client,
        auth_headers,
        title="Python Summit",
        event_date="2026-11-20T10:00:00Z",
    )
    await create_event(
        client,
        auth_headers,
        title="Python Workshop",
        event_date="2026-11-21T10:00:00Z",
    )
    await create_event(
        client,
        auth_headers,
        title="Garden Summit",
        event_date="2026-11-20T12:00:00Z",
    )

    response = await client.get("/events?title=python&date=2026-11-20&limit=1")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Python Summit"]
