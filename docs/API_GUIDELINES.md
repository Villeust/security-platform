# API Guidelines

This document defines baseline API rules for Security Platform modules. Existing endpoints should align with these conventions as the platform evolves.

## REST

APIs should be resource-oriented and use HTTP semantics consistently.

| Method | Usage |
| --- | --- |
| `GET` | Read resources. |
| `POST` | Create resources or execute explicit commands. |
| `PATCH` | Partially update resources. |
| `DELETE` | Remove resources where deletion is supported. |

## UUID

Primary identifiers should use UUID values for public API contracts. UUIDs keep identifiers opaque and stable across modules.

## snake_case

JSON request and response fields should use `snake_case`.

Examples:

- `facility_id`
- `work_type_ids`
- `request_number`
- `created_at`

## HTTP Status Codes

| Code | Meaning |
| --- | --- |
| `200 OK` | Successful read or update. |
| `201 Created` | Resource created. |
| `204 No Content` | Successful action with no body. |
| `400 Bad Request` | Invalid request format or unsupported operation. |
| `404 Not Found` | Resource does not exist. |
| `409 Conflict` | Business or uniqueness conflict. |
| `422 Unprocessable Entity` | Validation error. |
| `500 Internal Server Error` | Unexpected server error. |

## Validation

Validation should happen at the boundary through Pydantic schemas and inside services for business rules that require database context.

Examples:

- required fields;
- UUID format;
- entity existence;
- relationship consistency;
- module-specific business constraints.

## Pagination

List endpoints should support pagination before datasets become large.

Recommended parameters:

- `limit`
- `offset`

Responses should remain predictable and should not expose unbounded datasets by default.

## Filtering

Filtering parameters should be explicit and documented in OpenAPI.

Examples:

- `city_id`
- `facility_id`
- `status`
- `is_active`

## Error Responses

Error responses should be structured, stable and useful for frontend handling.

Recommended shape:

```json
{
  "detail": "Human-readable error message"
}
```

When a module needs richer errors, introduce a consistent extended shape rather than ad hoc responses.

## Versioning

API routes should remain versioned under a stable prefix such as `/api/v1`. Breaking changes should be introduced through a new version or a controlled migration path.

## OpenAPI

FastAPI-generated Swagger/OpenAPI documentation is part of the developer contract. Endpoints, schemas, status codes and examples should remain clear enough for new module teams to integrate quickly.

## Dependency Injection

Use FastAPI dependencies for shared concerns such as database sessions, authentication context and module-level access checks.

## Repository Pattern

Repository boundaries should be introduced where query complexity or reuse justifies it. Simple modules may use SQLAlchemy session operations directly inside service functions, but complex data access should be isolated.

## Service Layer

Business logic should live in service functions or service classes, not in frontend components or API route handlers. Services should coordinate validation, state transitions, assignments and persistence.
