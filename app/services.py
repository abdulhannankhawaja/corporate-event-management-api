"""Application business logic and database queries."""

from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.models import Event, Registration, User
from app.schemas import EventCreate, EventUpdate, RegistrationCreate, UserCreate
from app.security import hash_password, verify_password


async def check_database(db: AsyncSession) -> None:
    """Verify that the database accepts queries."""
    await db.execute(text("SELECT 1"))


async def create_event(db: AsyncSession, event_in: EventCreate) -> Event:
    """Create and persist an event."""
    event = Event(**event_in.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_events(
    db: AsyncSession,
    skip: int,
    limit: int,
    title: str | None = None,
    event_day: date | None = None,
) -> list[Event]:
    """List filtered events ordered by date and identifier."""
    statement = select(Event)
    if title:
        statement = statement.where(Event.title.ilike(f"%{title}%"))
    if event_day:
        day_start = datetime.combine(event_day, datetime.min.time())
        next_day = day_start + timedelta(days=1)
        statement = statement.where(
            Event.event_date >= day_start,
            Event.event_date < next_day,
        )
    statement = (
        statement.order_by(Event.event_date.asc(), Event.id.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


async def get_event(db: AsyncSession, event_id: int) -> Event:
    """Return an event or raise a not-found error."""
    event = await db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    return event


async def update_event(
    db: AsyncSession,
    event_id: int,
    event_in: EventUpdate,
) -> Event:
    """Apply provided fields and update an event."""
    event = await get_event(db, event_id)
    updates = event_in.model_dump(exclude_unset=True)
    if "max_capacity" in updates:
        result = await db.execute(
            select(func.count())
            .select_from(Registration)
            .where(Registration.event_id == event_id)
        )
        registration_count = int(result.scalar_one())
        if updates["max_capacity"] < registration_count:
            raise ConflictError(
                "Cannot reduce capacity below the current registration count"
            )
    for field, value in updates.items():
        setattr(event, field, value)
    await db.commit()
    await db.refresh(event)
    return event


async def delete_event(db: AsyncSession, event_id: int) -> None:
    """Delete an event or raise a not-found error."""
    event = await get_event(db, event_id)
    try:
        await db.execute(delete(Registration).where(Registration.event_id == event_id))
        await db.delete(event)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise


async def register_for_event(
    db: AsyncSession,
    event_id: int,
    data: RegistrationCreate,
) -> Registration:
    """Register an attendee for an event with capacity protection."""
    result = await db.execute(
        select(Event).where(Event.id == event_id).with_for_update()
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundError("Event not found")

    email = str(data.attendee_email).lower()
    duplicate_result = await db.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.attendee_email == email,
        )
        .limit(1)
    )
    if duplicate_result.scalar_one_or_none() is not None:
        raise ConflictError("Already registered for this event")

    count_result = await db.execute(
        select(func.count())
        .select_from(Registration)
        .where(Registration.event_id == event_id)
    )
    if int(count_result.scalar_one()) >= event.max_capacity:
        raise ConflictError("Event is full")

    registration = Registration(
        event_id=event_id,
        attendee_name=data.attendee_name,
        attendee_email=email,
    )
    db.add(registration)
    try:
        await db.commit()
        await db.refresh(registration)
        return registration
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Already registered for this event")


async def list_registrations(
    db: AsyncSession,
    event_id: int,
    skip: int,
    limit: int,
) -> list[Registration]:
    """List registrations for an existing event."""
    event = await db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    result = await db.execute(
        select(Registration)
        .where(Registration.event_id == event_id)
        .order_by(Registration.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def cancel_registration(
    db: AsyncSession,
    registration_id: int,
) -> None:
    """Cancel an existing registration."""
    registration = await db.get(Registration, registration_id)
    if registration is None:
        raise NotFoundError("Registration not found")
    await db.delete(registration)
    await db.commit()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Return a user by username, if one exists."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Create a user or raise a conflict for a duplicate username."""
    if await get_user_by_username(db, user_in.username) is not None:
        raise ConflictError("Username is already taken")
    user = User(
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Username is already taken") from exc
    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    """Authenticate credentials with a uniform failure message."""
    user = await get_user_by_username(db, username)
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect username or password")
    return user
