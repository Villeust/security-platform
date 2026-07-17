# Changelog

All notable changes to Security Platform are documented here. The root `VERSION`
file remains the authoritative application version source.

## Unreleased

This section represents work completed after the existing `v0.8.0` Git tag. It
belongs to the post-v0.8.0 development line and is not an official v0.9.0
release.

### Added

- Platform-wide correlation IDs.
- Structured logging.
- Standardized API error envelope.
- Readiness and version endpoints.
- Platform Doctor 2.0.
- Migration validation CLI.
- Version CLI.
- Global and route-level React error boundaries.
- Centralized frontend API error parsing.
- Correlation reference support in the frontend.
- Route-level lazy loading.
- Frontend async-safety hooks.

### Changed

- Hardened startup and stop scripts.
- Centralized platform version handling.
- Improved frontend bundle splitting.
- Strengthened environment validation.
- Standardized loading and error states.

### Security

- Centralized security headers.
- Hardened CSP, CORS and cookies.
- CSRF route coverage validation.
- Request and upload limits.
- Safer attachment download headers.
- Production configuration fail-fast checks.

### Fixed

- Database rollback handling.
- Inconsistent API error formats.
- Duplicate frontend error notifications.
- Repeated-submit risks.
- Stale async requests.
- Version mismatch across platform components.

## 0.8.0

The `v0.8.0` Git tag already exists and must not be recreated, moved,
overwritten or deleted. The historical v0.8.0 milestone captured the platform
foundation available at that tag:

- Security Platform shell with FastAPI backend and React/TypeScript frontend.
- Contractor Requests module with request lifecycle, assignments, comments,
  attachments, work results and history.
- Contractor Portal with tenant-scoped request/task/profile views.
- Internal dashboard and shared design-system foundation.
- Administration surfaces for contractors, users, roles, reference data,
  audit, system status and connection settings.
- Local authentication, cookie sessions, CSRF protection, password lifecycle
  and RBAC foundation.
- SQLite development database with Alembic migrations and a PostgreSQL
  production target documented as planned infrastructure.

Post-tag stabilization work is intentionally recorded under `Unreleased`.
