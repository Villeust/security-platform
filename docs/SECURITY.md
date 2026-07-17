# Security

Security Platform includes implemented security controls for local
pre-production development. This document describes actual controls and known
gaps without claiming production completion.

## Implemented Controls

### Cookie Authentication

Local users authenticate with cookie sessions. Auth state is not stored as a
browser localStorage token.

### CSRF

State-changing API routes require CSRF validation unless explicitly exempted by
the backend. The test suite includes CSRF route coverage checks.

### RBAC

Backend dependencies enforce role and permission checks. Frontend visibility is
permission-aware but is not the security boundary.

### Tenant Isolation

Contractor users are scoped to contractor memberships. Contractor Portal APIs
return tenant-safe data and must not expose foreign contractor data.

### Password Policy

Local authentication supports password policy validation, temporary password
flow, forced password change, password expiry configuration and account lockout.

### Correlation IDs

Correlation IDs flow through request handling, logs, audit/workflow records
where technically available and response headers. Frontend errors can display a
correlation reference for support.

### Structured Logging And Redaction

The backend uses a centralized logging pipeline with development console output
and production JSON output. Logs should avoid secrets and sensitive payloads.

### Security Headers

The backend emits centralized security headers, including CSP configuration,
frame restrictions and other browser hardening headers appropriate to the
environment.

### CORS

CORS configuration validates allowed origins. Production configuration rejects
unsafe localhost or wildcard-style origin settings.

### Cookies

Cookie settings vary by environment. Production configuration must use secure
cookie attributes and HTTPS-aware settings.

### Request And Upload Limits

Backend request and upload limits protect against oversized JSON and multipart
payloads. Reverse proxies should enforce equal or stricter limits in production.

### Safe File Downloads

Attachment download responses use safer filenames and headers and preserve
tenant/permission checks.

### Standardized Errors

API errors use a standardized envelope with machine-readable codes,
correlation ID, timestamp and request path. Raw internal payloads and secrets
must not be exposed.

### Production Configuration Validation

Production startup validates required security settings and fails fast on
unsafe defaults.

## Optional Integrations

SMTP, LDAP and ADFS configuration can be present or intentionally disabled.
They remain optional for readiness when disabled by configuration.

## Not Yet Production Complete

- External penetration test.
- Real production secrets manager.
- Redis-backed distributed rate limiting.
- Antivirus or malware scanning for uploads.
- Production LDAP/ADFS validation.
- Centralized SIEM/log transport.
- PostgreSQL migration and high availability.
- Backup and disaster recovery plan.
- Production monitoring and alerting.
- Formal incident-response process.

## Release Guidance

Do not claim production readiness until the production-hardening items above
are completed, validated and approved.
