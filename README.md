# Security Platform

Security Platform is an active-development, pre-production platform foundation
for enterprise physical security operations.

Current application version: `0.8.0`

- Existing Git release/tag: `v0.8.0`
- Current development line: post-v0.8.0 stabilization
- Current branch for this pass: `feature/release-readiness`
- Recommended next milestone: `v0.9.0`

The current untagged state is not an official v0.9.0 release and should not be
described as production ready.

Release governance note: the repository already contains a historical `v0.9.0`
tag. Do not create or move release tags until the project owner resolves the
future tag naming policy.

## Overview

Security Platform provides a shared internal workspace, Contractor Portal,
administration, local authentication, RBAC, audit/history foundations, Workflow
Engine, Workflow Center and operational diagnostics. Contractor Requests is the
first business module built on the platform.

## Implemented Modules

| Area | Status |
| --- | --- |
| Foundation | Implemented |
| Contractor Requests | Implemented |
| Contractor Portal | Implemented |
| Administration and RBAC | Implemented |
| Local authentication | Implemented |
| Internal dashboard and design system | Implemented |
| Platform Workflow Engine | Implemented |
| Workflow Center | Implemented |
| Platform stabilization A-D | Implemented |
| Release readiness / Phase E | Current |
| Notification Center | Planned |
| Scheduler | Planned |

## Security Capabilities

- Cookie-based authentication.
- CSRF protection on state-changing requests.
- RBAC and permission-aware routes/actions.
- Contractor tenant isolation.
- Password policy, temporary password flow and account lockout.
- Correlation IDs across request/response, logs, audit and workflow records
  where supported.
- Structured logging with development console and production JSON modes.
- Security headers, CSP, CORS and cookie hardening.
- Request and upload limits.
- Safe attachment download headers.
- Standardized API error envelope.
- Production configuration validation.

## Architecture

- Frontend: React, TypeScript, Vite, React Router, Ant Design and shared
  design-system primitives.
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic and service-layer modules.
- Database: SQLite for local development. PostgreSQL is a planned production
  target, not the active local configuration.
- Operations: PowerShell start/stop scripts, Platform Doctor, migration
  validation, readiness and version endpoints.

## Quick Start

Start the development environment:

```powershell
.\start-dev.cmd
```

Start with demo seed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -Seed
```

Force restart only verified project processes and seed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -ForceRestart -Seed
```

Stop the development environment:

```powershell
.\stop-dev.cmd
```

## Development Commands

Backend tests:

```powershell
cd backend
uv run pytest
```

Frontend tests and build:

```powershell
cd frontend
npm.cmd test
npm.cmd run build
```

Platform Doctor:

```powershell
cd backend
uv run python -m app.scripts.platform_doctor
uv run python -m app.scripts.platform_doctor --summary
uv run python -m app.scripts.platform_doctor --json
uv run python -m app.scripts.platform_doctor --fix
```

Version and migration validation:

```powershell
cd backend
uv run python -m app.scripts.version
uv run python -m app.scripts.validate_migrations
uv run python -m app.scripts.recover_partial_workflow_migration --dry-run
```

## Local URLs

| Service | URL |
| --- | --- |
| Frontend | http://127.0.0.1:3000 |
| Backend API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/v1/health |
| Readiness | http://127.0.0.1:8000/api/v1/readiness |
| Version | http://127.0.0.1:8000/api/v1/version |

## Documentation

- [Documentation Index](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [API Guidelines](docs/API_GUIDELINES.md)
- [Workflow Engine](docs/WORKFLOW_ENGINE.md)
- [Roadmap](docs/ROADMAP.md)
- [Releases](docs/releases/README.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## Roadmap Summary

Completed foundation work includes Contractor Requests, Workflow Engine,
Workflow Center, administration, RBAC, local authentication, Contractor Portal,
dashboard/design-system work and platform stabilization phases A-D.

Current work is Release Readiness / Phase E.

Next planned milestone: Notification Center and Scheduler for v0.9.0.

Planned production-hardening work includes production LDAP/ADFS validation,
reporting and SLA analytics, audit/security center, monitoring center,
PostgreSQL/Redis production infrastructure, CI/CD, deployment hardening and a
future v1.0 production release.

## License

No standalone license file is currently defined in this repository. Do not
assume an open-source license without explicit project owner approval.
