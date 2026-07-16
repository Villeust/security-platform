# Security

Security Platform uses cookie sessions, CSRF protection, RBAC and tenant checks. Phase B adds HTTP hardening around those existing controls without changing business behavior. Phase C adds operational validation around the same controls through Platform Doctor and startup checks.

## Security Headers

All backend responses receive:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Frame-Options`
- `Content-Security-Policy`
- `Permissions-Policy`

Development CSP allows local Vite connections and Swagger assets from `cdn.jsdelivr.net`. Production CSP is stricter and limits scripts, connections and framing to the application origin.

`Strict-Transport-Security` is emitted only when `ENVIRONMENT=production` and `HSTS_ENABLED=true`.

Auth, admin and attachment download responses use `Cache-Control: no-store`.

## CORS

`BACKEND_CORS_ORIGINS` must contain explicit HTTP or HTTPS origins. Wildcards are rejected because credentials are enabled.

Development may use configured localhost and `127.0.0.1` origins. Production rejects missing, malformed or localhost origins.

## Cookies

Session and refresh cookies are `HttpOnly`. The CSRF cookie remains readable by the frontend for the current double-submit CSRF design.

Cookies use:

- explicit `SameSite`;
- restricted `Path`;
- `Secure` in production;
- no `Domain` unless configured.

Logout deletes cookies with matching path, domain, secure and SameSite attributes.

## CSRF

Cookie-authenticated mutations require `X-CSRF-Token` matching the CSRF cookie and server-side session hash.

Documented exemptions:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`

Development identity headers are not cookie sessions. They are supported for local automation, with Workflow Center retaining explicit CSRF regression coverage for published mutation routes.

## Request And Upload Limits

Configurable limits:

- `MAX_REQUEST_BODY_BYTES`
- `MAX_JSON_BODY_BYTES`
- `MAX_MULTIPART_BODY_BYTES`
- `MAX_UPLOAD_FILE_BYTES`
- `MAX_FILES_PER_REQUEST`

Oversized requests return standardized `413` errors with correlation IDs. Attachment uploads also enforce file extension, MIME type, filename safety and the stricter of the legacy 20 MB limit and `MAX_UPLOAD_FILE_BYTES`.

Production reverse proxies should enforce matching or lower limits, for example `client_max_body_size` in Nginx.

## Pagination And Search

List endpoints use bounded `skip`, `limit` and search lengths. Sortable fields are explicit allowlists; arbitrary ORM attribute names are not accepted.

## Downloads

Protected attachment downloads use attachment disposition, controlled content type, `nosniff`, `no-store`, safe filenames and no filesystem path exposure.

## Production Validation

Production startup validates:

- explicit approved CORS origins;
- non-placeholder auth and encryption secrets;
- no localhost production origins;
- `PUBLIC_BASE_URL` must be HTTPS;
- `HSTS_ENABLED=true`;
- `ALLOW_DEV_AUTH_HEADERS=false`;
- `APP_DEBUG=false`;
- compatible cookie/HTTPS settings.

Secret values are never printed in validation errors.

Platform Doctor validates CSP, security headers, cookie configuration, CSRF route inventory and CORS configuration. JSON output reports only configured/not-configured flags and never prints secrets.

## Rate Limiting

Phase B adds configuration for a future rate-limiting layer. Distributed production enforcement should use a shared backend such as Redis. No scheduler, worker or Redis dependency is introduced in this phase.
