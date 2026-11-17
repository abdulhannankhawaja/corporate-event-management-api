"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

# Importing model definitions registers their tables before lifespan creates them.
from app import (
    models,  # noqa: F401
    services,
)
from app.db import Base, engine, get_db
from app.dependencies import PaginationDependency, get_current_user
from app.exceptions import AppError
from app.models import User
from app.schemas import (
    ErrorResponse,
    EventCreate,
    EventRead,
    EventUpdate,
    HealthRead,
    RegistrationCreate,
    RegistrationRead,
    Token,
    UserCreate,
    UserRead,
)
from app.security import create_access_token

db_dependency = Depends(get_db)
title_query = Query(
    default=None,
    description="Partial, case-insensitive event title match.",
    examples=["Python", "Annual"],
)
event_day_query = Query(
    default=None,
    alias="date",
    description="Calendar day in YYYY-MM-DD format.",
    examples=["2026-11-20"],
)


def error_response(description: str, example_detail: str) -> dict[str, object]:
    """Build a consistent OpenAPI error response with a representative example."""
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {"detail": example_detail},
            }
        },
    }


current_user_dependency = Depends(get_current_user)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables while the application starts."""
    del app
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Corporate Event Management API",
    description="API foundation for managing corporate events and registrations.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Events",
            "description": "Create, browse, update, and delete corporate events.",
        },
        {
            "name": "Registrations",
            "description": "Register attendees and manage event registrations.",
        },
        {
            "name": "Authentication",
            "description": "Create accounts and obtain bearer access tokens.",
        },
        {
            "name": "Health",
            "description": "Check API and database availability.",
        },
    ],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert application errors into JSON responses."""
    del request
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return validation errors using the documented readable detail shape."""
    del request
    details = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )
    detail = (
        f"Request validation failed: {details}"
        if details
        else ("Request validation failed")
    )
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get(
    "/health",
    tags=["Health"],
    summary="Check API database health",
    description="Run a database query and report application availability.",
    response_model=HealthRead,
    status_code=200,
    responses={
        500: error_response(
            "Database unavailable",
            "The database could not be reached.",
        )
    },
)
async def health(db: AsyncSession = db_dependency) -> HealthRead:
    """Check database availability and return a healthy status."""
    await services.check_database(db)
    return HealthRead(status="ok")


@app.post(
    "/events",
    tags=["Events"],
    summary="Create an event",
    description="Create a new corporate event.",
    response_model=EventRead,
    status_code=201,
    responses={
        401: error_response("Authentication required", "Not authenticated"),
        422: error_response("Invalid event data", "Request validation failed"),
    },
)
async def create_event(
    event_in: EventCreate,
    current_user: User = current_user_dependency,
    db: AsyncSession = db_dependency,
) -> EventRead:
    """Validate and create an event."""
    del current_user
    event = await services.create_event(db, event_in)
    return EventRead.model_validate(event)


@app.get(
    "/events",
    tags=["Events"],
    summary="List events",
    description=(
        "List events ordered by event date and identifier. "
        "Combine title and date filters with skip and limit pagination."
    ),
    response_model=list[EventRead],
    status_code=200,
    responses={
        422: error_response(
            "Invalid filter or pagination parameters",
            "Request validation failed",
        )
    },
)
async def list_events(
    pagination: PaginationDependency,
    title: str | None = title_query,
    event_day: date | None = event_day_query,
    db: AsyncSession = db_dependency,
) -> list[EventRead]:
    """List filtered and paginated events."""
    events = await services.list_events(
        db,
        pagination.skip,
        pagination.limit,
        title,
        event_day,
    )
    return [EventRead.model_validate(event) for event in events]


@app.get(
    "/events/{event_id}",
    tags=["Events"],
    summary="Get an event",
    description="Retrieve one event by its identifier.",
    response_model=EventRead,
    status_code=200,
    responses={
        404: error_response("Event not found", "Event not found"),
        422: error_response(
            "Invalid event identifier",
            "Request validation failed",
        ),
    },
)
async def get_event(
    event_id: int,
    db: AsyncSession = db_dependency,
) -> EventRead:
    """Retrieve an event."""
    event = await services.get_event(db, event_id)
    return EventRead.model_validate(event)


@app.put(
    "/events/{event_id}",
    tags=["Events"],
    summary="Update an event",
    description="Update the provided fields of an existing event.",
    response_model=EventRead,
    status_code=200,
    responses={
        404: error_response("Event not found", "Event not found"),
        401: error_response("Authentication required", "Not authenticated"),
        409: error_response(
            "Capacity conflict",
            "Cannot reduce capacity below the current registration count",
        ),
        422: error_response("Invalid event data", "Request validation failed"),
    },
)
async def update_event(
    event_id: int,
    event_in: EventUpdate,
    current_user: User = current_user_dependency,
    db: AsyncSession = db_dependency,
) -> EventRead:
    """Validate and update an event."""
    del current_user
    event = await services.update_event(db, event_id, event_in)
    return EventRead.model_validate(event)


@app.delete(
    "/events/{event_id}",
    tags=["Events"],
    summary="Delete an event",
    description="Delete an event by its identifier.",
    response_model=None,
    status_code=204,
    responses={
        404: error_response("Event not found", "Event not found"),
        401: error_response("Authentication required", "Not authenticated"),
        422: error_response(
            "Invalid event identifier",
            "Request validation failed",
        ),
    },
)
async def delete_event(
    event_id: int,
    current_user: User = current_user_dependency,
    db: AsyncSession = db_dependency,
) -> Response:
    """Delete an event."""
    del current_user
    await services.delete_event(db, event_id)
    return Response(status_code=204)


@app.post(
    "/events/{event_id}/registrations",
    tags=["Registrations"],
    summary="Register for an event",
    description="Register an attendee for an existing event.",
    response_model=RegistrationRead,
    status_code=201,
    responses={
        404: error_response("Event not found", "Event not found"),
        409: error_response(
            "Registration conflict",
            "Already registered for this event",
        ),
        422: error_response(
            "Invalid registration data",
            "Request validation failed",
        ),
    },
)
async def register_for_event(
    event_id: int,
    registration_in: RegistrationCreate,
    db: AsyncSession = db_dependency,
) -> RegistrationRead:
    """Validate and register an attendee."""
    registration = await services.register_for_event(
        db,
        event_id,
        registration_in,
    )
    return RegistrationRead.model_validate(registration)


@app.get(
    "/events/{event_id}/registrations",
    tags=["Registrations"],
    summary="List event registrations",
    description=(
        "List paginated registrations for an existing event using skip and limit."
    ),
    response_model=list[RegistrationRead],
    status_code=200,
    responses={
        404: error_response("Event not found", "Event not found"),
        422: error_response(
            "Invalid event identifier",
            "Request validation failed",
        ),
    },
)
async def list_registrations(
    event_id: int,
    pagination: PaginationDependency,
    db: AsyncSession = db_dependency,
) -> list[RegistrationRead]:
    """List paginated registrations for an event."""
    registrations = await services.list_registrations(
        db,
        event_id,
        pagination.skip,
        pagination.limit,
    )
    return [
        RegistrationRead.model_validate(registration) for registration in registrations
    ]


@app.delete(
    "/registrations/{registration_id}",
    tags=["Registrations"],
    summary="Cancel a registration",
    description="Cancel an existing event registration.",
    response_model=None,
    status_code=204,
    responses={
        404: error_response("Registration not found", "Registration not found"),
        422: error_response(
            "Invalid registration identifier",
            "Request validation failed",
        ),
    },
)
async def cancel_registration(
    registration_id: int,
    db: AsyncSession = db_dependency,
) -> Response:
    """Cancel a registration."""
    await services.cancel_registration(db, registration_id)
    return Response(status_code=204)


@app.post(
    "/auth/signup",
    tags=["Authentication"],
    summary="Create a user account",
    description="Create an account using a username and password.",
    response_model=UserRead,
    status_code=201,
    responses={
        409: error_response("Username is already taken", "Username is already taken"),
        422: error_response("Invalid signup data", "Request validation failed"),
    },
)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = db_dependency,
) -> UserRead:
    """Create an account without exposing password data."""
    user = await services.create_user(db, user_in)
    return UserRead.model_validate(user)


@app.post(
    "/auth/login",
    tags=["Authentication"],
    summary="Log in",
    description="Exchange OAuth2 password credentials for a bearer token.",
    response_model=Token,
    status_code=200,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "$ref": "#/components/schemas/Body_login_auth_login_post"
                    },
                    "examples": {
                        "credentials": {
                            "summary": "Example login credentials",
                            "value": {
                                "username": "jane.smith",
                                "password": "secure-password-123",
                            },
                        }
                    },
                }
            },
            "required": True,
        }
    },
    responses={
        401: error_response(
            "Incorrect username or password",
            "Incorrect username or password",
        ),
        422: error_response("Invalid login form", "Request validation failed"),
    },
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = db_dependency,
) -> Token:
    """Authenticate a user and issue a JWT access token."""
    user = await services.authenticate_user(
        db,
        form_data.username,
        form_data.password,
    )
    return Token(access_token=create_access_token(user.username))
