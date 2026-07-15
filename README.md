# Contractor Requests

Minimal runnable scaffold for Contractor Requests.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic Settings, pytest, uv
- Frontend: React, TypeScript, Vite, Ant Design, Axios, React Router
- Infrastructure: Docker Compose with backend, frontend, and PostgreSQL

## Run

Create `.env` from `.env.example`, then start the project:

```bash
docker compose up --build
```

Frontend: http://localhost:3000

Backend: http://localhost:8000

Swagger: http://localhost:8000/docs

Health: http://localhost:8000/api/v1/health

## Backend tests

```bash
cd backend
uv sync
uv run pytest
```

## Demo seed

Run the local demo seed explicitly:

```bash
cd backend
uv run python -m app.scripts.seed_demo
```

The seed is idempotent, so the same command can be repeated without creating duplicates:

```bash
uv run python -m app.scripts.seed_demo
```

Swagger: http://localhost:8000/docs

Example contractor API checks use the UUID values printed by the seed:

```bash
curl -H "X-Contractor-Id: <contractor-uuid>" http://localhost:8000/api/v1/contractor/requests
curl -H "X-Contractor-Id: <contractor-uuid>" http://localhost:8000/api/v1/contractor/requests/<request-uuid>
curl -X POST -H "X-Contractor-Id: <contractor-uuid>" http://localhost:8000/api/v1/contractor/requests/<request-uuid>/accept
```

## Frontend build

```bash
cd frontend
npm ci
npm run build
```
