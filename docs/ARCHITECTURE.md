# Architecture

Security Platform is a modular pre-production platform foundation for physical
security operations. The current local implementation uses a React frontend,
FastAPI backend and SQLite development database.

## Frontend

- React.
- TypeScript.
- Vite.
- React Router.
- Ant Design.
- Shared design-system primitives.
- Internal workspace.
- Contractor Portal.
- Workflow Center.
- Frontend stability utilities:
  - global and route-level error boundaries;
  - centralized API error parsing;
  - correlation reference support;
  - route-level lazy loading;
  - async-safety hooks for cancellation and duplicate-submit protection.

## Backend

- FastAPI application.
- SQLAlchemy models and sessions.
- Alembic migrations.
- Pydantic request/response schemas.
- Cookie authentication.
- CSRF protection.
- RBAC dependencies.
- Contractor tenant isolation.
- Workflow Engine.
- Workflow Center APIs.
- Audit/history recording.
- Outbox records.
- Structured logging.
- Correlation ID middleware.
- Health, readiness and version endpoints.
- Security middleware for headers, request limits and production configuration
  validation.

## Database

Local development uses SQLite through `backend/dev.db`. Alembic migrations are
the source of schema changes.

PostgreSQL is the documented production target, but it is not the active local
database in this repository state. Redis-backed distributed services are also
planned infrastructure, not current runtime dependencies.

## Modules

Implemented modules:

- Contractor Requests.
- Contractor Portal.
- Administration.
- RBAC and local authentication.
- Internal dashboard.
- Platform Workflow Engine.
- Workflow Center.
- Platform Doctor and operational scripts.

Planned modules:

- Notification Center.
- Scheduler.
- Reporting and SLA analytics.
- Monitoring Center.
- Audit and Security Center.

## Workflow Engine And Workflow Center

The Workflow Engine stores generic definitions, states, transitions, instances,
transition executions, SLA policies/timers and outbox events. It includes
idempotency and optimistic locking foundations.

Workflow Center exposes administrative and operational views for definitions,
versions, validation, instances, SLA, outbox, audit and platform health. It is
permission-protected and does not replace Contractor Requests public APIs.

Future workflow capabilities such as BPMN-like execution, scheduled
transitions, event-driven transitions, sub-workflows and external integrations
remain planned.

## Operational Foundation

The root `VERSION` file is authoritative. Backend metadata, OpenAPI,
`/api/v1/version`, readiness and frontend display should remain aligned to it.

Platform Doctor validates the local development environment, including Python,
database, Alembic, Workflow, RBAC, authentication, Contractor data, seed,
storage and configuration. Startup scripts consume Doctor output before
starting services.

## Boundaries

Frontend route guards improve user experience but are not a security boundary.
Backend authentication, RBAC, tenant isolation and CSRF enforcement remain the
source of truth.
