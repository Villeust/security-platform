# Notification Center

This document describes the Security Platform Notification Center foundation.
The current implementation is Phase 1 only.

## Implemented In Phase 1

Phase 1 adds the reusable notification domain foundation without changing the
legacy admin notification behavior.

Implemented objects:

- `NotificationTemplate`
- `NotificationEvent`
- `NotificationMessage`
- `NotificationDelivery`
- `NotificationPreference`

Implemented services:

- strict placeholder rendering with simple identifier placeholders only;
- recursive safe payload sanitization with redaction of sensitive keys;
- internal relative action URL validation;
- typed recipient resolver interfaces;
- explicit user and permission/role-based internal recipient resolvers;
- lazy notification preference policy;
- critical in-app override policy;
- event, message and delivery deduplication;
- opt-in legacy `AdminNotification` compatibility adapter;
- outbox bridge abstraction for controlled, caller-managed ingestion.

Transaction rule:

New notification services are caller-transaction-owned. They may add rows and
flush identifiers, but they do not call `commit()` or `rollback()`.

## Legacy AdminNotification Coexistence

`AdminNotification` remains fully operational and backward-compatible.

Phase 1 does not:

- alter the `admin_notifications` table;
- backfill historical admin notifications;
- automatically dual-write existing `create_notification()` calls;
- expose legacy rows through the generic notification domain;
- change admin dashboard notification queries;
- change admin notification API response shapes.

An opt-in compatibility adapter exists for future producers. It must be called
explicitly, participates in the caller transaction and uses idempotency.

## Domain Model

`NotificationTemplate` stores versioned template content. Published template
content is immutable; deactivation is allowed, and a new version is the update
path for published content.

`NotificationEvent` stores a safe event envelope with `deduplication_key` and
`payload_schema_version`. Unknown event types are handled without crashing.

`NotificationMessage` stores one user-visible notification for one explicit
recipient. Internal recipients must not have `tenant_id`; contractor recipients
must have `tenant_id` representing contractor/company scope.

`NotificationDelivery` stores channel pipeline records. Phase 1 creates only
pipeline records; it does not send email.

`NotificationPreference` is lazy: explicit preference rows override platform
defaults, but no seed creates preference rows for every user/category.

## Safety Rules

Templates:

- no eval, exec, imports or function calls;
- no dotted traversal;
- no brackets or indexing;
- no private or dunder placeholders;
- missing required values fail with controlled errors.

Payloads:

- dictionaries, lists, tuples and scalar values are supported;
- depth, item count and string length are bounded;
- unsupported objects are rejected;
- sensitive keys are replaced with `[REDACTED]`.

Action URLs:

- only relative internal paths are allowed;
- allowed prefixes are `/applications/`, `/workflow/`, `/admin/` and
  `/contractor/`;
- external origins, protocol-relative URLs, `javascript:`, `data:`, `file:`,
  backslashes and control characters are rejected.

## Event Contracts

Phase 1 registers declared event contracts separately from operational support.
An event is operational only when both producer and recipient policy are
implemented.

Most platform event types are declared for compatibility planning. Phase 1 only
implements a controlled explicit test contract used by service tests. Business
event producers are deferred unless they already have a safe mapping.

## Outbox Bridge

The bridge is an abstraction:

`DomainEventOutbox -> NotificationEvent -> Recipient Resolution -> NotificationMessage -> NotificationDelivery`

Phase 1 does not run a background processor. Unsupported outbox events are left
unprocessed. Supported controlled events can be ingested by an explicit caller
inside a caller-managed transaction.

## Permissions

Phase 1 adds notification permissions idempotently.

`PLATFORM_ADMIN` receives all notification permissions.

`SECURITY_ADMIN` receives operational/template/delivery/preference permissions,
but not scheduler permissions in Phase 1.

`SECURITY_OPERATOR` receives `notifications.view` only.

`VIEWER` receives `notifications.view` for future own-notification viewing.

Contractor roles receive no internal notification administration permissions.

## Planned For Phase 2

- User-facing notification APIs.
- Admin APIs for templates, events, deliveries, failed deliveries and
  statistics.
- Internal Notification Center UI.
- Header unread badge and dropdown.
- Contractor-safe notification APIs and portal UI.
- Preference APIs and profile pages.

## Planned For Phase 3

- Delivery processor.
- SMTP email channel using existing encrypted SMTP configuration.
- Retry policy and manual retry.
- Safe provider error redaction.

## Planned For Phase 4

- Scheduler abstraction and job models.
- Dedicated worker process model.
- Scheduled jobs for outbox, events, deliveries, deadlines, SLA, password
  expiry and platform health.
- Platform Doctor scheduler checks.

No scheduler, APScheduler integration or background worker is implemented in
Phase 1.

## Planned For Phase 5

- Administration section for notifications and jobs.
- Operational monitoring pages.
- Retention reporting.
- Extension guide for new event sources and delivery channels.
