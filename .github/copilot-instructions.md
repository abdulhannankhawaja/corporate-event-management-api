# Project rules: Corporate Event Management API (Acme Corp)
This is a graded university assignment. Follow these rules in every task.

## Stack
Python 3.12, FastAPI, SQLAlchemy 2.0 async (asyncpg), PostgreSQL 16, Pydantic v2, PyJWT, pwdlib[argon2], pytest + pytest-asyncio + httpx.

## Structure (package app/)
- config.py: Settings via pydantic-settings, read from env/.env. No secrets in code.
- db.py: async engine, async_sessionmaker(expire_on_commit=False), Base, get_db dependency.
- models.py: SQLAlchemy 2.0 models with Mapped/mapped_column: User, Event, Registration.
- schemas.py: Pydantic v2. Separate Create / Update / Read schemas per resource.
- services.py: ALL business logic and ALL database queries, as async functions taking an AsyncSession.
- exceptions.py: AppError base (status_code, detail) with NotFoundError 404, ConflictError 409, UnauthorizedError 401.
- security.py: password hashing and JWT create/decode. Pure functions, no DB access.
- main.py: app, lifespan (creates tables), AppError handler, and thin route functions. Routes only validate input, call ONE service function, and return. No queries or business rules in routes.

## Code rules
- Every module, class and function has a docstring. Comments explain WHY. PEP 8, full type hints, meaningful names, no duplicated logic.
- Only async DB calls with await. Never a sync Session. Do not use lazy-loaded relationships; use explicit queries.
- Services raise exceptions from exceptions.py. Never catch bare Exception.
- Every route sets tags, summary, description, response_model, status_code, and `responses` for its error codes.
- Every error body is {"detail": "<readable message>"}.
- Datetimes: schema validators convert timezone-aware values to naive UTC (asyncpg rejects aware values for timestamp columns).

## Domain contract
Event: id, title, description (optional), event_date, location, max_capacity (> 0).
Registration: id, event_id (FK, ON DELETE CASCADE), attendee_name, attendee_email (stored lowercase), created_at. UNIQUE(event_id, attendee_email).
User: id, username (unique), hashed_password.

Endpoints (auth = needs Bearer token):
POST /events (auth) 201 | GET /events 200 | GET /events/{id} 200/404 | PUT /events/{id} (auth) 200/404/409 | DELETE /events/{id} (auth) 204/404
POST /events/{id}/registrations 201/404/409 | GET /events/{id}/registrations 200/404 | DELETE /registrations/{id} 204/404
POST /auth/signup 201/409 | POST /auth/login (OAuth2 form) 200/401 | GET /health 200
Reads and registration endpoints are public. 401 includes header WWW-Authenticate: Bearer.

Business rules (enforced in services.py):
1. Registering for a missing event -> 404.
2. Same email twice for one event, case-insensitive -> 409.
3. Event full -> 409. Lock the event row (SELECT ... FOR UPDATE) before counting, to prevent overbooking.
4. Lowering max_capacity below the current registration count -> 409.
5. Deleting an event deletes its registrations in the same transaction.

## Working rules for the agent
- Do NOT run git commands. Do NOT add packages that were not requested.
- After changing code, run the app or tests to verify, and report what you ran and the result.
- Stay within the task. Do not refactor unrelated files.