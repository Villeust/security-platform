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

## Frontend build

```bash
cd frontend
npm ci
npm run build
```
