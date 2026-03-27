# Iclinic Auth Service

## Overview
The `auth-service` is the centralized identity and access management microservice for the Iclinic backend. It provides robust user management, roles, and issues standard JWT access and refresh tokens.

## Architecture
- **API Layer**: Exposes RESTful endpoints under `/api/v1`.
- **Middleware**: Injects global rate-limiters (`slowapi`), custom `AppError` exception catchers, structured logging, and observability instrumentation (OpenTelemetry + Prometheus).
- **Service Layer**: Houses the core domain logic for hashing passwords and managing roles.
- **Repository/Data Layer**: Asynchronous SQLAlchemy 2.0 sessions (`asyncpg`) talking to a PostgreSQL database.

## Tech Stack
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL with `asyncpg` and SQLAlchemy
- **Security**: Argon2/Bcrypt password hashing, JWT (python-jose)
- **Dependency Management**: `uv` and `pyproject.toml`
- **Observability**: OpenTelemetry + Prometheus Fastapi Instrumentator

## Folder Structure
- `src/api/rest/routes/`: FastAPI routers for each domain (auth, users, health).
- `src/core/services/`: Business logic decoupled from HTTP request/response.
- `src/core/exceptions/`: Centralized `AppError` hierarchy.
- `src/data/models/`: SQLAlchemy ORM classes.
- `docs/`: Technical documentation (this folder).

## Setup Instructions
1. **Install Dependencies**: Using `uv pip install -e .[dev]`
2. **Environment Variables**: Copy `.env.example` to `.env` and fill valid SECRETS.
3. **Database Migration**: Run `alembic upgrade head`.
4. **Run Locally**: Execute `uvicorn src.api.rest.app:app --host 0.0.0.0 --port 8000 --reload`

## Key Features
- Secure `/register` and `/login` handling.
- Access restrictions via JWT authorization headers.
- Automatic rate-limiting (10/min) on critical public endpoints.
