# Next Release

## Overview

The current repository state is post-v0.8.0 development work on top of the
existing `v0.8.0` tag. It is not an official v0.9.0 release.

Recommended next milestone: `v0.9.0`.

Release governance warning: the repository already contains a historical
`v0.9.0` Git tag. Treat `v0.9.0` here as the preferred milestone label, not as
permission to create or move a tag.

## Highlights

- Platform reliability, security and operations hardening.
- Platform Doctor 2.0 and migration validation.
- Version consistency and readiness checks.
- Frontend stability, route-level error boundaries and lazy loading.
- Release-readiness documentation and validation.

## Architecture

Post-tag work strengthens the existing architecture without adding new business
modules. The platform now has clearer foundations for:

- correlation IDs across request, logs, audit and response headers;
- structured logging and standardized error responses;
- readiness/version metadata;
- operational diagnostics through Platform Doctor;
- frontend error containment and async safety.

## Security

The development line includes hardened security headers, CORS validation, CSRF
coverage tests, request/upload limits, safe attachment headers, standardized
errors and production configuration fail-fast checks.

## Compatibility

The work intentionally preserves:

- Contractor Requests business logic and statuses;
- RequestHistory semantics;
- assignment workflow;
- Contractor Portal tenant isolation;
- Workflow Engine and Workflow Center behavior;
- authentication, RBAC and CSRF behavior;
- public API routes and migration history.

## Validation

Validation results are recorded in
[PHASE_E_ACCEPTANCE.md](PHASE_E_ACCEPTANCE.md). This document should be updated
when additional acceptance runs are performed.

## Known Limitations

- Browser-level visual validation requires a browser automation stack or manual
  review.
- Production infrastructure, backups, HA, monitoring and centralized log
  transport remain planned.
- Notification Center and Scheduler are not implemented in this development
  line.

## Upgrade Notes

For local development:

```powershell
.\start-dev.cmd
powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -Seed
```

For migration validation:

```powershell
cd backend
uv run python -m app.scripts.validate_migrations
```

## Rollback Notes

Rollback planning must include a database backup, application checkout, service
stop/start sequence and validation through Platform Doctor. Existing tags must
not be moved.

## Next Milestone

The next milestone should focus on Notification Center and Scheduler:

- notification domain model;
- templates;
- recipient resolution;
- in-app notifications;
- email channel;
- outbox processing;
- retries;
- scheduling;
- SLA reminders;
- password-expiry notifications;
- delivery audit;
- channel preferences.
