"""Pydantic request and response schemas."""

from datetime import UTC, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


def convert_to_naive_utc(value: datetime) -> datetime:
    """Convert an aware datetime to naive UTC."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def validate_non_blank(value: str, field_name: str) -> str:
    """Strip text and reject an empty or whitespace-only value."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


class EventCreate(BaseModel):
    """Validate data used to create an event."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    event_date: datetime
    location: str = Field(min_length=1, max_length=200)
    max_capacity: int = Field(gt=0)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        """Strip and validate the event title."""
        return validate_non_blank(value, "title")

    @field_validator("location")
    @classmethod
    def location_must_not_be_blank(cls, value: str) -> str:
        """Strip and validate the event location."""
        return validate_non_blank(value, "location")

    @field_validator("event_date")
    @classmethod
    def event_date_must_be_naive_utc(cls, value: datetime) -> datetime:
        """Normalize the event date to naive UTC."""
        return convert_to_naive_utc(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Annual Company Summit",
                "description": "A full-day leadership and strategy summit.",
                "event_date": "2026-11-20T10:00:00Z",
                "location": "Main Conference Hall",
                "max_capacity": 150,
            }
        }
    )


class EventUpdate(BaseModel):
    """Validate optional event update fields."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    event_date: datetime | None = None
    location: str | None = Field(default=None, min_length=1, max_length=200)
    max_capacity: int | None = Field(default=None, gt=0)

    @field_validator(
        "title",
        "event_date",
        "location",
        "max_capacity",
        mode="before",
    )
    @classmethod
    def reject_null_for_non_nullable_fields(cls, value: object) -> object:
        """Reject explicit nulls while allowing these optional fields to be omitted."""
        if value is None:
            raise ValueError("This field cannot be null")
        return value

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        """Strip and validate an optional event title."""
        if value is not None:
            return validate_non_blank(value, "title")
        return value

    @field_validator("location")
    @classmethod
    def location_must_not_be_blank(cls, value: str | None) -> str | None:
        """Strip and validate an optional event location."""
        if value is not None:
            return validate_non_blank(value, "location")
        return value

    @field_validator("event_date")
    @classmethod
    def event_date_must_be_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Normalize an optional event date to naive UTC."""
        if value is not None:
            return convert_to_naive_utc(value)
        return value

    @model_validator(mode="after")
    def reject_empty_update(self) -> "EventUpdate":
        """Reject an update body that contains no fields."""
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "location": "East Conference Center",
                "max_capacity": 175,
            }
        }
    )


class EventRead(BaseModel):
    """Represent an event returned by the API."""

    id: int
    title: str
    description: str | None
    event_date: datetime
    location: str
    max_capacity: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "title": "Annual Company Summit",
                "description": "A full-day leadership and strategy summit.",
                "event_date": "2026-11-20T10:00:00",
                "location": "Main Conference Hall",
                "max_capacity": 150,
            }
        },
    )


class RegistrationCreate(BaseModel):
    """Validate data used to register an attendee."""

    attendee_name: str = Field(min_length=1, max_length=100)
    attendee_email: EmailStr

    @field_validator("attendee_name")
    @classmethod
    def attendee_name_must_not_be_blank(cls, value: str) -> str:
        """Strip and validate the attendee name."""
        return validate_non_blank(value, "attendee_name")

    @field_validator("attendee_email")
    @classmethod
    def attendee_email_must_be_lowercase(cls, value: EmailStr) -> str:
        """Store the normalized attendee email in lowercase."""
        return str(value).lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "attendee_name": "Aisha Khan",
                "attendee_email": "aisha.khan@example.com",
            }
        }
    )


class RegistrationRead(BaseModel):
    """Represent a registration returned by the API."""

    id: int
    event_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "event_id": 1,
                "created_at": "2026-11-17T10:30:00",
            }
        },
    )


class UserCreate(BaseModel):
    """Validate credentials used to create a user."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "jane.smith",
                "password": "secure-password-123",
            }
        }
    )


class UserRead(BaseModel):
    """Represent a user without exposing password data."""

    id: int
    username: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "username": "jane.smith",
            }
        },
    )


class HealthRead(BaseModel):
    """Represent the API health check response."""

    status: str

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "ok"}},
    )


class Token(BaseModel):
    """Represent an OAuth2 bearer access token."""

    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": (
                    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                    "eyJzdWIiOiJqYW5lLnNtaXRoIiwiZXhwIjoxODAwMDAwMDAwfQ."
                    "example-signature"
                ),
                "token_type": "bearer",
            }
        }
    )


class ErrorResponse(BaseModel):
    """Represent a documented API error response."""

    detail: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": "A readable error message."},
        }
    )
