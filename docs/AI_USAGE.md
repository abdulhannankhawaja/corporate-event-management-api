# Tools

- Copilot SDK in VS Code, using Agent mode
- Claude conversation for planning and prompt design
- Python and pip for the virtual environments and dependency checks
- FastAPI/Uvicorn, Docker Compose/PostgreSQL, curl, pytest, and Ruff for implementation verification
- VS Code workspace tools and shell commands for reading and editing project files
- Git for the initial scaffolding commit and push

# Models

- Copilot model reported by the host: `mai-code-2-flash`, later switched to `gpt-6-luna`.
- Claude conversation: used for planning and prompt design.

# Settings

- Copilot mode: Agent
- Instructions file: `.github/copilot-instructions.md`
- Application settings: values are loaded from `.env`; `.env` is ignored by Git.

# Prompts used

## Prompt 1

```text
un `git add -A && git commit -m "chore: add project structure and Copilot rules" && git push`. This scaffolding commit on main is fine.
```

## Prompt 2

```text
Also create `docs/AI_USAGE.md` now with headings **Tools**, **Models**, **Settings**, **Prompts used**, **Chat history**. Paste each prompt under “Prompts used” as you run it, and write down the Copilot model, the mode (Agent) and the instructions file. Also note that this Claude conversation was used for planning and prompt design.
```

## Prompt 3

```text
Read .github/copilot-instructions.md and follow it.

Task: project foundation only. No models or business endpoints yet.

1. In the active venv, install: fastapi, "uvicorn[standard]", "sqlalchemy[asyncio]>=2.0,<2.1", asyncpg, "pydantic[email]", pydantic-settings, pyjwt, "pwdlib[argon2]", python-multipart. Dev tools: pytest, pytest-asyncio, httpx, aiosqlite, ruff. Then run `pip freeze > requirements.txt`.
2. docker-compose.yml: service "db" using postgres:16, database event_db, user/password postgres/postgres, port 5432, a named volume, and a pg_isready healthcheck.
3. .env.example with DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/event_db, SECRET_KEY=replace-with-a-long-random-string, ACCESS_TOKEN_EXPIRE_MINUTES=30. Copy it to .env. Make sure .gitignore contains .env, .venv, __pycache__, .pytest_cache, .ruff_cache.
4. app/config.py: Settings class with those three values.
5. app/db.py: async engine, async_sessionmaker(expire_on_commit=False), Base (DeclarativeBase), and get_db async-generator dependency.
6. app/exceptions.py: AppError (status_code, detail), NotFoundError, ConflictError, UnauthorizedError.
7. app/models.py: module docstring only for now.
8. app/services.py: module docstring plus `async def check_database(db)` that runs SELECT 1.
9. app/main.py: FastAPI app with title, description and version; a lifespan that creates all tables via `conn.run_sync(Base.metadata.create_all)` (import models so tables register); an exception handler that converts AppError into JSONResponse {"detail": ...} (add the WWW-Authenticate: Bearer header for 401); GET /health (tag "Health") that calls services.check_database and returns {"status": "ok"}.
10. Verify: run `docker compose up -d db`, then `uvicorn app.main:app --reload`, call /health, and report the result.

Every file needs docstrings and comments per the rules.
```

## Prompt 4

```text
**You verify:** `docker compose up -d db`, then `uvicorn app.main:app --reload`, then open `/health` and `/docs`. If Docker isn’t available, use `sudo apt-get update && sudo apt-get install -y postgresql`, create the `event_db` database, and adjust `DATABASE_URL`.

**Commits:** `chore: pin dependencies and docker-compose for postgres` · `feat: async db engine, config and exception base` · `feat: app skeleton with lifespan and health check`

**You should be able to explain:** why `expire_on_commit=False`, what `lifespan` does, and why `get_db` uses `yield`.
```

## Prompt 5

```text
Read .github/copilot-instructions.md and follow it.

Task: Event CRUD (M2, M5 for events, M6).

models.py: Event with id, title (String 200, indexed), description (Text, nullable), event_date (naive DateTime, indexed), location (String 200), max_capacity (int).

schemas.py:
- EventCreate: title (min 1, max 200, stripped, must not be blank), description optional, event_date datetime, location (min 1, max 200, stripped, not blank), max_capacity (gt 0). All required except description.
- EventUpdate: every field optional with the same constraints; a validator rejects a body with no fields.
- EventRead: from_attributes, includes id.
- A shared validator converts timezone-aware event_date to naive UTC.
- Add realistic example payloads (json_schema_extra) to each schema.

services.py: create_event, list_events (order by event_date then id; no filters yet), get_event (raise NotFoundError "Event not found"), update_event (apply only provided fields via model_dump(exclude_unset=True)), delete_event.

main.py: the five /events routes with tag "Events", summaries, descriptions, response_model, status codes (POST 201, GET 200, PUT 200, DELETE 204 with no body) and `responses` documenting 404/422. No authentication yet. Routes stay thin.

Verify: run the app and exercise every endpoint with curl, including a 404 on a missing id, a 422 for an empty title and for max_capacity 0, and a timezone-aware date like "2026-11-20T10:00:00Z". Report the results.

Every file needs docstrings and comments per the rules.
```

## Prompt 6

```text
**Commits:** `feat: event model and schemas with validation` · `feat: event service layer` · `feat: event CRUD routes` · `docs: swagger examples for event schemas`

**You should be able to explain:** the difference between the Create, Update and Read schemas, what `exclude_unset` does, and why the route doesn’t touch the DB.
```

## Prompt 7

```text
Read .github/copilot-instructions.md and follow it.

Task: event registrations and business rules (M3, M4).

models.py: Registration with id, event_id (FK events.id, ondelete CASCADE, indexed), attendee_name (String 100), attendee_email (String 255), created_at (server_default now), and UniqueConstraint("event_id", "attendee_email", name="uq_event_email").

schemas.py: RegistrationCreate (attendee_name min 1 max 100 stripped; attendee_email EmailStr, lowercased by a validator) and RegistrationRead (from_attributes; id, event_id, created_at). Add examples.

services.py:
- register_for_event(db, event_id, data): select the event with .with_for_update(); missing -> NotFoundError; same event + email already registered -> ConflictError("Already registered for this event"); registration count >= max_capacity -> ConflictError("Event is full"); insert and commit. Also catch IntegrityError on commit, roll back, and raise the same duplicate ConflictError.
- list_registrations(db, event_id): 404 if the event does not exist.
- cancel_registration(db, registration_id): 404 if missing.
- Update delete_event to delete the event's registrations first in the same transaction (explicit delete statement, no lazy loading).
- Update update_event: if max_capacity is lowered below the current registration count raise ConflictError.

main.py: POST /events/{id}/registrations (201), GET /events/{id}/registrations (200), DELETE /registrations/{id} (204). Tag "Registrations", summaries, descriptions, response models, and `responses` for 404/409/422.

Verify with curl: register successfully, register the same email in a different case (409), fill the event to capacity then register again (409), register for event 9999 (404), send a malformed email (422), cancel a registration (204), delete an event that has registrations (204 and registrations are gone). Report results.

Every file needs docstrings and comments per the rules.
```

## Prompt 8

```text
Read .github/copilot-instructions.md and follow it.

Task: pagination (B1) and search/filtering (B2).

- Add a reusable pagination dependency (a small dataclass or Annotated dependency) with skip (int, default 0, ge 0) and limit (int, default 10, ge 1, le 100), so the same definition is reused instead of duplicated.
- GET /events: add optional `title` (partial, case-insensitive match using ilike) and `date` (a date such as 2026-11-20). The date filter matches every event on that calendar day using the range [day 00:00, next day 00:00). Filters combine with each other and with skip/limit. Keep the query building inside services.list_events. In the route, name the parameter `event_day` with alias="date" so it does not shadow the `date` type.
- GET /events/{id}/registrations also accepts skip/limit.
- Update Swagger descriptions and examples for the new parameters.

Verify with curl: limit=2, skip=2, title=python (case-insensitive), date=2026-11-20, title+date+limit combined, limit=0 and limit=1000 and skip=-1 (all 422). Report results.
```

## Prompt 9

```text
**Commits:** `feat: reusable pagination dependency` · `feat: title and date filters for events`
```

## Prompt 10

```text
Read .github/copilot-instructions.md and follow it.

Task: JWT authentication (B3).

- models.py: User (id, username unique and indexed, hashed_password).
- schemas.py: UserCreate (username 3-50, password 8-128), UserRead (id, username), Token (access_token, token_type="bearer"). Never return the password hash.
- security.py: hash_password and verify_password using pwdlib PasswordHash.recommended(); create_access_token(subject) with an exp claim from settings (HS256, secret from settings.SECRET_KEY); decode_access_token that raises on invalid or expired tokens.
- services.py: create_user (ConflictError if username taken), authenticate_user (UnauthorizedError "Incorrect username or password" for wrong user or wrong password, same message for both), get_user_by_username.
- main.py: POST /auth/signup (201) and POST /auth/login using OAuth2PasswordRequestForm (returns Token), both with tag "Authentication". Define oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False) and a get_current_user dependency that raises UnauthorizedError for a missing, invalid or expired token or an unknown user, so the error body matches every other error. Protect POST, PUT and DELETE /events with this dependency. GET endpoints and all registration endpoints stay public. Add 401 to `responses` for protected routes.
- Make config require SECRET_KEY from the environment (no insecure default). Update .env.example to explain how to generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"

Verify: signup, login, create event without a token (401), with a token (201), with a garbage token (401), GET /events without a token (200), duplicate signup (409). Confirm the Authorize button works in /docs. Report results.
```

## Prompt 11

```text
**Commits:** `feat: user model, schemas and password hashing` · `feat: login and signup endpoints` · `feat: protect event write routes with JWT`

**You should be able to explain:** what’s inside a JWT, why hashing differs from encrypting, and why the secret lives in `.env`.
```

## Prompt 12

```text
Read .github/copilot-instructions.md and follow it.

Task: pytest suite (B5). It must run without PostgreSQL.

- pytest.ini: asyncio_mode = auto, asyncio_default_fixture_loop_scope = function, testpaths = tests.
- tests/conftest.py: a per-test in-memory SQLite engine (sqlite+aiosqlite://, StaticPool, check_same_thread False), create tables with Base.metadata.create_all, override app's get_db dependency, and yield an httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test"). Fixtures: `client`, `auth_headers` (signs up and logs in; login uses form data via data=, not json=), and `event` (an event created through the API). Clear dependency_overrides and dispose the engine afterwards.
- tests/test_events.py: create (201), list, get one, update (200), delete (204 then 404); 404 on a missing id; 422 for empty/whitespace title, max_capacity 0 and -5, missing required fields, invalid date; timezone-aware date accepted; pagination (limit, skip, limit=0 -> 422); title filter case-insensitive; date filter; filters combined.
- tests/test_registrations.py: register (201); list; cancel (204); duplicate email in a different case (409); event full (409); non-existent event (404); invalid email (422); cancel a missing registration (404); lowering capacity below registrations (409); deleting an event removes its registrations.
- tests/test_auth.py: signup (201), duplicate username (409), login success, wrong password (401), POST/PUT/DELETE /events without a token (401), with an invalid token (401), GET /events public (200), password is never present in any response.
- Use descriptive test names and short docstrings. Use parametrize for the validation cases.

Run `pytest -v`. If a test fails because of an application bug, fix the application, not the test. Never weaken a test to make it pass. Save the final output with `pytest -v | tee docs/test-results.txt`.
```

## Prompt 13

```text
**Commits:** `test: fixtures and in-memory database setup` · `test: event endpoints and validation` · `test: registration rules` · `test: authentication and protected routes`
```

## Prompt 14

```text
Read .github/copilot-instructions.md and follow it.

Task: finish OpenAPI documentation (M7) and code-quality cleanup (M8). Do not change behaviour.

1. FastAPI(...): add openapi_tags with a description for Events, Registrations, Authentication, Health.
2. A shared ErrorResponse schema ({"detail": str}) used in `responses` of every route for its documented error codes, with an example message each (404, 409, 401, 422).
3. Check that every route has summary, description, response_model, status_code and examples for request bodies. Fill any gap.
4. Audit every file for missing module, class and function docstrings and for comments that explain why. Add what is missing. Remove duplicated logic.
5. Run `ruff check --fix .` and `ruff format .`, resolve any remaining warnings, then run `pytest -q` to confirm nothing broke. Report what you changed.
```

## Prompt 15

```text
**You verify:** open `/docs` and check that every endpoint has a description, an example and its error responses.

**Commits:** `docs: openapi tags, error schema and examples` · `style: docstrings, comments and ruff formatting`
```

## Prompt 16

```text
Read .github/copilot-instructions.md and follow it.

Task: write README.md (M10). Write it in plain, human-sounding prose, not marketing language.

Sections: project overview (2-3 sentences); features; tech stack; project structure; prerequisites; installation (clone, venv, pip install -r requirements.txt); database setup (docker compose up -d db, plus a fallback for a locally installed PostgreSQL, and how to set DATABASE_URL and SECRET_KEY in .env); running the app (uvicorn app.main:app --reload, docs at http://127.0.0.1:8000/docs, and how to open the forwarded port in Codespaces); authentication walkthrough (signup, login, Authorize in Swagger); endpoint table with auth requirement and status codes; business rules; running tests (pytest -v, note they use in-memory SQLite and need no PostgreSQL); design decisions (async, row locking, naive UTC dates, no Alembic and why); AI usage (point to docs/AI_USAGE.md).

Then check that requirements.txt matches what the code imports, and that a fresh clone would work by following the README exactly.
```

# Chat history

This VS Code Copilot SDK chat was used to implement the repository changes. A separate Claude conversation was used for planning and prompt design.

The VS Code transcript has not yet been exported. To add the requested exported history, use the Command Palette → **Chat: Export Chat…** and save the export under `docs/` (for example, `docs/chat-history.md`), then link it here. This workspace editor cannot invoke the VS Code Command Palette.

## Manual screenshots

The requested Swagger screenshots have not been captured. A browser/screenshot UI is not available in this environment, so no screenshot files or README image links have been fabricated. Capture the requested endpoint examples in Swagger UI and save the real images under `docs/screenshots/`; then add their links to the README.

## Prompt 17

```text
**Screenshots (manual, 10 min).** Save these to `docs/screenshots/` and link them from the README:

#Screenshot01`/docs` overview with all endpoints02–03signup and login (200 and the token)04Authorize dialog filled in05–09events: POST 201, GET list, GET one, PUT 200, DELETE 20410–12registrations: POST 201, GET list, DELETE 20413duplicate registration (409)14event full (409)15non-existent event (404)16POST event without a token (401)17validation error (422)18pagination and filter in use19pytest output

Finish `docs/AI_USAGE.md`: tools, models, settings, every prompt, and the exported chat history (Command Palette → **Chat: Export Chat…**). Disclose this Claude conversation as well.

**Commits:** `docs: README with setup, database and test instructions` · `docs: AI usage log` · `docs: swagger screenshots`
```
