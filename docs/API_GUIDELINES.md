# API Guidelines

Swagger/OpenAPI is the endpoint source of truth:

http://127.0.0.1:8000/docs

## Version Prefix

Public API routes use the `/api/v1` prefix. Breaking API changes should use a
new version or an explicit migration path.

## Authentication

APIs use cookie authentication for browser sessions. Do not introduce token
storage in browser localStorage for authenticated application flows.

## CSRF

State-changing routes require CSRF validation unless explicitly exempted by the
backend. Mutation clients must send the expected CSRF header/token.

## Standard Error Envelope

API errors should use the centralized error envelope:

- machine-readable error code;
- message;
- detail where safe;
- correlation ID;
- timestamp;
- request path.

Do not add ad-hoc `HTTPException(detail="...")` responses for new code when a
centralized application error exists.

## Correlation IDs

Clients may send a valid correlation ID header. The backend returns the active
correlation ID in the response and includes it in logs and audit/workflow
records where technically available.

## Validation

Validation failures should return structured 422 responses through the standard
error handling path. Validation messages must not expose secrets.

## Pagination

List endpoints should use explicit page/size or offset/limit parameters with
server-side maximums. Avoid unbounded list responses for operational data.

## Sorting And Filtering

Sort fields must use explicit allowlists. Do not pass arbitrary client-provided
field names into ORM order clauses.

## Idempotency

Use idempotency keys where supported by the Workflow Engine and other mutation
surfaces that need safe retry behavior.

## Response Models

Routes should return explicit response schemas instead of raw ORM objects.
Contractor-facing APIs must use tenant-safe DTOs.

## Backward Compatibility

Preserve existing public API routes, Contractor Requests behavior, approved
statuses, RequestHistory semantics, assignment workflow, tenant isolation,
authentication behavior, RBAC and CSRF semantics unless a change is explicitly
approved.

## Health, Readiness And Version

Operational endpoints:

- `GET /api/v1/health`
- `GET /api/v1/readiness`
- `GET /api/v1/version`

Readiness verifies core runtime dependencies and should not fail for optional
SMTP, LDAP or ADFS integrations when they are intentionally disabled.
