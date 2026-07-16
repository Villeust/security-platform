# Architecture

Security Platform построена как единое веб-приложение с разделением ответственности между frontend, API, сервисной логикой, слоем доступа к данным и PostgreSQL.

```mermaid
flowchart TD
    User[User]
    FE[Frontend<br/>React + TypeScript]
    API[Backend API<br/>FastAPI]
    Services[Services]
    Repositories[Repositories]
    Database[(PostgreSQL)]

    User --> FE
    FE --> API
    API --> Services
    Services --> Repositories
    Repositories --> Database
```

## Application Layers

| Layer | Responsibility |
| --- | --- |
| Frontend | Web interface, routing, forms, dashboards and user workflows. |
| Backend API | REST endpoints, request validation, OpenAPI documentation and dependency wiring. |
| Services | Business logic, orchestration, validation rules and module behavior. |
| Repositories | Data access boundary and query encapsulation where the module needs it. |
| Database | PostgreSQL persistence managed through SQLAlchemy and Alembic migrations. |

## Separation of Responsibilities

The platform keeps business logic out of UI components and avoids coupling HTTP handlers directly to persistence details. API routes expose module capabilities, services coordinate business operations, and database models represent persisted state.

Current implementation already follows this direction in the Contractor Requests module:

- API routes expose request, reference data, contractor and health endpoints.
- Service logic validates request scope, applies premise contacts and assigns contractors by work type.
- SQLAlchemy models define persisted entities and relationships.
- Alembic manages schema evolution.

## Module Structure

```mermaid
flowchart LR
    Platform[Security Platform]
    Platform --> Core[Core Platform]
    Platform --> Modules[Modules]

    Core --> API[API Foundation]
    Core --> UI[Frontend Shell]
    Core --> Data[Database and Migrations]
    Core --> Tools[Developer Toolkit]

    Modules --> CR[Contractor Requests]
    Modules --> AC[Access Control<br/>Planned]
    Modules --> CCTV[CCTV<br/>Planned]
    Modules --> VM[Visitor Management<br/>Planned]
    Modules --> IM[Incident Management<br/>Planned]
    Modules --> MON[Monitoring<br/>Planned]
    Modules --> REP[Reports & Analytics<br/>Planned]
```

Contractor Requests is the first implemented business module. Planned modules should reuse the same platform foundation instead of introducing isolated applications.

## Frontend and Backend Interaction

Frontend communicates with Backend API over HTTP. Backend responses are documented through Swagger/OpenAPI and should remain stable, versioned and predictable.

| Direction | Description |
| --- | --- |
| Frontend to API | UI sends JSON requests to REST endpoints. |
| API to Services | Routes delegate business decisions to service functions. |
| Services to Database | Services validate and persist data through SQLAlchemy sessions and model relationships. |
| API to Frontend | API returns structured JSON responses and standard HTTP status codes. |

## Platform Scalability

Security Platform is designed to scale by adding modules around a shared core:

- shared routing and API conventions;
- shared frontend design system and navigation patterns;
- shared database migration process;
- consistent module boundaries;
- common developer scripts and documentation;
- clear roadmap for workflow, authentication, notifications, monitoring and reports.

The goal is to grow Security Platform into a portfolio of security services while keeping operational and development practices unified.

## Operational Foundation

The platform version is governed by the root `VERSION` file. Backend metadata, OpenAPI, `/api/v1/version`, readiness and frontend version displays synchronize to that source and package metadata is kept aligned.

Platform Doctor is the local operational diagnostic utility. It groups checks into Core, Security, Infrastructure and Optional Integrations, then retains detailed diagnostics for database, Alembic, Workflow Engine, RBAC, auth, contractor data, seed, storage and migration recovery. Startup scripts consume Doctor JSON and abort on errors unless `-Force` is explicitly supplied.

Development startup and stop scripts are part of the platform foundation. Startup validates migrations, Doctor health, backend readiness, health, version and frontend reachability. Stop only targets processes that can be verified as belonging to the current repository and reports Windows access-denied conditions without killing unrelated Python or Node processes.

## Workflow Engine And Workflow Center

The generic Workflow Engine is a platform service, not a Contractor Requests subsystem. Its persistence model stores workflow definitions, states, transitions, instances, transition executions, SLA policies and timers, idempotency records and outbox events. Business modules connect through adapter boundaries so the engine can observe and validate module entities without taking over module APIs.

Workflow Center is the administrative and operational surface for that engine. It is exposed under `/api/v1/admin/workflow-center` and `/admin/workflow-center`, guarded by existing RBAC permissions such as `workflows.view`, `workflows.manage`, `workflows.publish`, `workflows.instances.view` and `workflows.sla.view`. Read views are generic and safe for operators: definition catalog, version list, validation, instance explorer, SLA center, outbox monitor, process audit and platform health.

Phase 3 deliberately does not redesign Contractor Requests. Existing request APIs, approved statuses, assignment workflow, request history, Contractor Portal behavior, authentication, RBAC and tenant isolation remain the source of truth. The architecture keeps room for future parallel workflows, sub-workflows, scheduled transitions, event-driven transitions, external integrations and BPMN-like execution without implementing those capabilities in this phase.
