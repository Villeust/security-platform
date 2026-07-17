# Release Checklist

Use this checklist before creating or promoting a release. Do not mark
production-only steps complete during local validation.

## Repository

- [ ] Worktree is clean.
- [ ] No secrets are present.
- [ ] No generated artifacts are tracked.
- [ ] Correct branch is selected.
- [ ] Version is consistent across root, backend, frontend and docs.

## Backend

- [ ] Full pytest suite passes.
- [ ] Alembic current revision matches head.
- [ ] Migration validation passes.
- [ ] Seed is idempotent on an isolated migrated database.
- [ ] Platform Doctor normal, summary, JSON and safe fix modes run.
- [ ] Health, readiness and version endpoints respond.

## Frontend

- [ ] Frontend tests pass.
- [ ] TypeScript check passes.
- [ ] Production build passes.
- [ ] Route smoke passes.
- [ ] Bundle summary is recorded.

## Security

- [ ] CSRF coverage is validated.
- [ ] CORS configuration is reviewed.
- [ ] Cookie flags are appropriate for the target environment.
- [ ] Security headers are reviewed.
- [ ] Payload and upload limits are configured.
- [ ] Error responses avoid secret or raw payload exposure.

## Documentation

- [ ] README is current.
- [ ] Roadmap is current.
- [ ] Changelog is current.
- [ ] Release notes are current.
- [ ] Architecture documentation is current.
- [ ] Security documentation is current.
- [ ] Development commands are current.

## Git

- [ ] Pull request is approved.
- [ ] `develop` is updated.
- [ ] `main` merge is approved.
- [ ] Tag name is verified.
- [ ] Existing `v0.9.0` tag conflict is resolved before any future v0.9.0 tag.
- [ ] Existing tags are not overwritten.

## Deployment

- [ ] Production configuration is reviewed.
- [ ] Secrets are provisioned outside Git.
- [ ] Database backup exists.
- [ ] Migration plan is approved.
- [ ] Rollback plan is approved.
- [ ] Monitoring and alerting are ready.
