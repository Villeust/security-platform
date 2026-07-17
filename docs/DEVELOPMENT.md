# Development Guide

Security Platform is currently version `0.8.0` and in post-v0.8.0
pre-production development.

## Start

```powershell
.\start-dev.cmd
```

Start with demo seed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -Seed
```

Force restart verified project processes and seed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -ForceRestart -Seed
```

Stop:

```powershell
.\stop-dev.cmd
```

The startup script checks tooling, ports, stale runtime state, migrations,
Platform Doctor, backend readiness/health/version and frontend reachability.
Startup continues with warnings and aborts on errors unless forced.

## Backend

```powershell
cd backend
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Backend tests:

```powershell
cd backend
uv run pytest
```

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 3000
```

Frontend tests:

```powershell
cd frontend
npm.cmd test
```

Frontend build:

```powershell
cd frontend
npm.cmd run build
```

## Platform Doctor

Platform Doctor verifies the development environment before startup and after
upgrades.

```powershell
cd backend
uv run python -m app.scripts.platform_doctor
uv run python -m app.scripts.platform_doctor --summary
uv run python -m app.scripts.platform_doctor --json
uv run python -m app.scripts.platform_doctor --fix
```

Safe fix mode may recreate runtime/storage folders and clear stale runtime
files. It must not delete databases, stamp Alembic, run migrations, change
passwords, insert seed or modify business data.

## Version

The root `VERSION` file is authoritative. Backend metadata, OpenAPI,
`/api/v1/version`, readiness metadata, package metadata and frontend display
must remain aligned.

```powershell
cd backend
uv run python -m app.scripts.version
```

## Migration Validation

```powershell
cd backend
uv run python -m app.scripts.validate_migrations
```

Partial workflow migration recovery dry run:

```powershell
cd backend
uv run python -m app.scripts.recover_partial_workflow_migration --dry-run
```

## URLs

| Service | URL |
| --- | --- |
| Frontend | http://127.0.0.1:3000 |
| Backend API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/v1/health |
| Readiness | http://127.0.0.1:8000/api/v1/readiness |
| Version | http://127.0.0.1:8000/api/v1/version |

## Development Database

Local development uses SQLite at `backend/dev.db`. Do not commit local database
files, SQLite temporary files or workflow recovery backups.

## Git Flow

- Work on feature branches.
- Target reviewed work at `develop`.
- Keep `main` for approved release states.
- Do not move or recreate existing release tags.

## Documentation Rule

No documentation change should imply production readiness unless the related
production controls are implemented, validated and approved.
