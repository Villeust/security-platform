# Roadmap

Security Platform is in active pre-production development. This roadmap reflects
the actual implemented repository state and avoids marking planned capabilities
as complete before they exist.

## Completed

- Foundation.
- Contractor Requests.
- Workflow and collaboration.
- Administration and RBAC.
- Local authentication.
- Contractor Portal.
- Unified internal dashboard and design system.
- Platform Workflow Engine.
- Workflow Center.
- Platform Stabilization A-D.

## Current

- Release Readiness / Phase E.

## Next

Notification Center and Scheduler are the recommended `v0.9.0` milestone.

Scope preview:

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

## Planned

- Production LDAP/ADFS validation.
- Reporting and SLA analytics.
- Audit and Security Center.
- Monitoring Center.
- PostgreSQL/Redis production infrastructure.
- CI/CD and deployment hardening.
- v1.0 production release.

## Version Notes

- Current application version: `0.8.0`.
- Existing Git tag: `v0.8.0`.
- Current development line: post-v0.8.0 stabilization.
- Recommended next milestone: `v0.9.0`.
- Governance warning: a historical `v0.9.0` Git tag already exists and must be
  resolved before any future tag is created.

Do not call the current untagged development state an official v0.9.0 release.

## Not Implemented Yet

- Notification Center as a platform service.
- Scheduler.
- BPMN execution.
- Scheduled workflow transitions.
- Event-driven workflow automation.
- External workflow integrations.
- PostgreSQL/Redis production deployment.
- Production monitoring and centralized log transport.
