# Contributing

Security Platform is in active pre-production development. Contributions should
keep behavior explicit, testable and compatible with existing modules.

## Branches

- Use feature branches named `feature/<short-topic>`.
- Keep `develop` as the integration branch for reviewed work.
- Keep `main` reserved for approved release states.

## Commits

- Use concise imperative commit messages.
- Keep unrelated changes in separate commits.
- Do not commit generated artifacts, local databases, secrets, logs or runtime
  folders.

## Pull Requests

- Describe the user-visible scope and any migration or security impact.
- Include backend and frontend validation results that match the changed area.
- Link documentation updates when behavior, operations or security posture
  changes.

## Tests

- Backend changes should run `uv run pytest` from `backend`.
- Frontend changes should run `npm.cmd test` and `npm.cmd run build` from
  `frontend`.
- Migration changes should run `uv run python -m app.scripts.validate_migrations`.

## Migrations

- Never edit historical migrations after they are shared.
- Never add destructive migrations without explicit review and rollback notes.
- Test migration idempotency and seed behavior on an isolated database.

## Security

- Do not commit secrets or real credentials.
- Preserve RBAC, tenant isolation, CSRF and authentication behavior unless the
  change is explicitly approved as a security change.
- Avoid leaking raw payloads, stack traces or secrets in API responses and logs.

## Documentation

- Keep README, roadmap, security, development and release notes aligned with
  the actual implementation.
- Do not claim production readiness until production-hardening items are
  completed and approved.
