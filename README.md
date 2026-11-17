# Corporate Event Management API

## Project overview

This project is an asynchronous API for creating corporate events and managing attendee registrations. Users can create, update, and delete events after signing in; event and registration reads are public.

## Features

- Create, list, search, update, and delete events.
- Filter events by part of the title or by calendar date, and paginate list responses.
- Register attendees, list registrations, and cancel registrations.
- Sign up and authenticate with JWT bearer tokens.
- Check database connectivity at `/health`.

## Tech stack

The API uses Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg, and PostgreSQL 16. Passwords are hashed with pwdlib and Argon2; JWTs are signed with PyJWT. The tests use pytest, HTTPX, and in-memory SQLite.

## Project structure

```text
app/
  config.py          Environment-backed settings
  db.py              Async SQLAlchemy engine, base, and session dependency
  dependencies.py    Shared pagination dependency
  exceptions.py      Application error types
  main.py            FastAPI app, routes, and error handling
  models.py          Event, Registration, and User tables
  schemas.py         Request and response schemas
  security.py        Password hashing and JWT helpers
  services.py        Database queries and business rules
tests/
  conftest.py        Per-test in-memory SQLite and API fixtures
  test_auth.py       Authentication and authorization tests
  test_events.py     Event endpoint and validation tests
  test_openapi.py    OpenAPI documentation tests
  test_registrations.py Registration behavior tests
docs/
  AI_USAGE.md        AI tools, settings, and prompts used
  test-results.txt   Saved verbose pytest output
docker-compose.yml   Local PostgreSQL service
pytest.ini           Pytest configuration
requirements.txt     Pinned runtime and development dependencies
```

## Prerequisites

- Python 3.12 and `venv`
- Docker with the Compose plugin, or a local PostgreSQL 16 installation
- Git

On Debian or Ubuntu, install the Python virtual-environment support package if
it is not already present:

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv
```

## Installation

Clone the repository and create an isolated Python environment:

```bash
git clone https://github.com/abdulhannankhawaja/corporate-event-management-api.git
cd corporate-event-management-api
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Create a local environment file and set a private signing key:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the generated value into the `SECRET_KEY` entry in `.env`. Keep `.env` private and do not commit it. The example database URL uses the credentials configured by the included Compose file; adjust `DATABASE_URL` if you use different database credentials or a different host.

## Database setup

Start the included PostgreSQL 16 service:

```bash
docker compose up -d db
docker compose ps
```

Wait for the `db` service to report `healthy`. The Compose service creates the `event_db` database with username `postgres` and password `postgres` and stores its data in a named volume.

For a locally installed PostgreSQL server, create the database and set a password for the `postgres` role if needed:

```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres createdb event_db
```

Use the following values in `.env` for that local setup:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/event_db
SECRET_KEY=<the generated secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

If you choose a different database user, password, host, or port, update `DATABASE_URL` to match. URL-encode special characters in credentials.

## Running the app

From the activated virtual environment and repository root, start the API:

```bash
uvicorn app.main:app --reload
```

Open the interactive Swagger UI at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The OpenAPI document is at `/openapi.json`; the database health check is at `/health`.

In GitHub Codespaces, run Uvicorn with `--host 0.0.0.0` so the port can be forwarded:

```bash
uvicorn app.main:app --reload --host 0.0.0.0
```

Open the **Ports** panel in VS Code, find port `8000`, and select its forwarded address (or use **Open in Browser**) to reach `/docs`.

The app creates missing tables at startup. Keep PostgreSQL running while using API routes.

## Authentication walkthrough

1. In Swagger, expand `POST /auth/signup`, enter a username and password, and execute the request. A successful signup returns `201`.
2. Expand `POST /auth/login` and enter the same credentials as form fields. A successful login returns an access token.
3. Select **Authorize** near the top of Swagger UI, enter the login credentials in the OAuth2 form, and authorize. Swagger will send the bearer token with protected event-write requests.
4. `POST /events`, `PUT /events/{event_id}`, and `DELETE /events/{event_id}` require a valid token. Reads and all registration endpoints are public.

The login endpoint uses OAuth2 password form data (`application/x-www-form-urlencoded`), not a JSON body. Signup accepts JSON.

## Endpoints

| Method | Path | Auth required | Success | Documented errors |
|---|---|---:|---:|---|
| `GET` | `/health` | No | `200` | `500` |
| `POST` | `/auth/signup` | No | `201` | `409`, `422` |
| `POST` | `/auth/login` | No | `200` | `401`, `422` |
| `POST` | `/events` | Yes | `201` | `401`, `422` |
| `GET` | `/events` | No | `200` | `422` |
| `GET` | `/events/{event_id}` | No | `200` | `404`, `422` |
| `PUT` | `/events/{event_id}` | Yes | `200` | `401`, `404`, `409`, `422` |
| `DELETE` | `/events/{event_id}` | Yes | `204` | `401`, `404`, `422` |
| `POST` | `/events/{event_id}/registrations` | No | `201` | `404`, `409`, `422` |
| `GET` | `/events/{event_id}/registrations` | No | `200` | `404`, `422` |
| `DELETE` | `/registrations/{registration_id}` | No | `204` | `404`, `422` |

`GET /events` accepts optional `title` and `date` filters plus `skip` and `limit`. `GET /events/{event_id}/registrations` accepts `skip` and `limit`. The limit must be between 1 and 100.

## Business rules

- An event must exist before attendees can register.
- An attendee email is stored in lowercase and can register only once per event.
- Registrations cannot exceed an event's capacity. The service locks the event row before checking capacity.
- Event capacity cannot be lowered below the current number of registrations.
- Deleting an event deletes its registrations in the same transaction.
- User responses never include password hashes. Authentication errors use a consistent JSON `detail` field; 401 responses include `WWW-Authenticate: Bearer`.

## Running tests

Activate the virtual environment and run:

```bash
pytest -v
```

The tests create a fresh in-memory SQLite database per test and do not require PostgreSQL or Docker. Ruff is available for linting and formatting:

```bash
ruff check .
ruff format --check .
```

## Design decisions

- **Async database access:** FastAPI handlers and SQLAlchemy sessions use async operations so request handling does not block on database I/O.
- **Row locking:** Registration checks lock the event row with `SELECT ... FOR UPDATE` before counting attendees. This prevents concurrent registrations from passing the capacity check at the same time on PostgreSQL.
- **Naive UTC dates:** Request schemas convert timezone-aware event dates to naive UTC before persistence because the database columns use timestamps without time zones.
- **No Alembic yet:** This foundation creates missing tables from SQLAlchemy metadata at application startup. Alembic was left out to avoid adding migration tooling before there are versioned schema changes; `create_all` does not update existing tables, so migrations should be introduced when schema evolution is needed.

## AI usage

See [docs/AI_USAGE.md](docs/AI_USAGE.md) for the tools, settings, prompts, and chat-history note.
