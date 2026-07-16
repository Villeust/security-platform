# Roadmap

Security Platform is in active development. The roadmap separates completed foundation work from planned platform capabilities.

| Version | Scope | Status |
| --- | --- | --- |
| v0.4 | Security Platform Foundation | Done |
| v0.5 | Workflow Engine foundation and Workflow Center | In progress |
| v0.6 | Attachments, Comments, Notifications | Planned |
| v0.7 | Authentication, Roles, Permissions | Planned |
| v0.8 | Contractor Portal | Planned |
| v0.9 | Monitoring, Reports | Planned |
| v1.0 | Production Release | Future |

## v0.4

Status: Done

- Core FastAPI backend.
- React and TypeScript frontend.
- PostgreSQL persistence.
- Alembic migrations.
- Swagger/OpenAPI documentation.
- Docker Compose support.
- Developer start/stop scripts.
- Health check endpoint.
- Demo seed.
- Contractor Requests MVP.

## v0.5

Status: In progress

- Generic backend Workflow Engine foundation.
- Contractor Request workflow integration through adapters while preserving existing request APIs.
- Platform Doctor diagnostics for environment, migrations, RBAC, seed data and workflow health.
- Workflow Center for definitions, versions, validation, instances, SLA, outbox, audit and platform health.
- Not included yet: Phase 4 automation, scheduled transitions, event-driven transitions, external integrations, BPMN-like execution or visual diagram authoring.

## v0.6

Status: Planned

- Attachments.
- Comments.
- Notifications.

## v0.7

Status: Planned

- Authentication.
- Roles.
- Permissions.

## v0.8

Status: Planned

- Contractor Portal.
- Contractor-facing workflows.
- Contractor request visibility and actions.

## v0.9

Status: Planned

- Monitoring.
- Reports.
- Analytics-oriented views.

## v1.0

Status: Future

- Production Release.
- Stabilized platform baseline.
- Operational readiness.

## Long-term Vision

Security Platform should become a unified enterprise environment for physical security operations. Long-term development should focus on:

- expanding the module catalog;
- connecting operational security workflows;
- improving observability and reporting;
- standardizing access, roles and approvals;
- keeping a single user experience across all security services;
- supporting future integration with enterprise systems where required.
