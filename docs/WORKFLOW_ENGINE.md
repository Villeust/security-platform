# Workflow Engine

The Workflow Engine is a platform backend service for workflow-enabled modules. It stores generic workflow definitions and runtime state while business modules keep ownership of their own APIs, data model and business rules.

## Current Scope

Implemented foundation:

- workflow definitions, versions, states and transitions;
- workflow instances and transition execution log;
- SLA policies and timers;
- idempotency records and optimistic locking;
- outbox events with safe operational metadata;
- adapter boundary for module-specific validation and side effects;
- RBAC permissions for workflow definition, publication, instance and SLA access;
- Workflow Center admin and operations UI.

Contractor Requests is integrated as the first workflow-enabled module, but existing Contractor Request APIs, statuses, assignment behavior, request history and Contractor Portal behavior remain intact.

## Data Model

Core tables:

- `workflow_definitions`
- `workflow_states`
- `workflow_transitions`
- `workflow_instances`
- `workflow_transition_executions`
- `workflow_idempotency_records`
- `workflow_sla_policies`
- `workflow_sla_timers`
- `domain_event_outbox`

Definitions are versioned by `code` and `version`. Instances reference a specific definition version and use `entity_type`, `entity_id` and `instance_key` so future modules can run more than one workflow for the same business entity.

## Backend API

Generic operational API:

```text
GET /api/v1/admin/workflow-center/dashboard
GET /api/v1/admin/workflow-center/definitions
GET /api/v1/admin/workflow-center/definitions/{definition_id}
GET /api/v1/admin/workflow-center/definitions/{definition_id}/validation
GET /api/v1/admin/workflow-center/definitions/{definition_id}/export
GET /api/v1/admin/workflow-center/versions
GET /api/v1/admin/workflow-center/versions/diff
GET /api/v1/admin/workflow-center/instances
GET /api/v1/admin/workflow-center/instances/{instance_id}
GET /api/v1/admin/workflow-center/sla
GET /api/v1/admin/workflow-center/outbox
GET /api/v1/admin/workflow-center/audit
GET /api/v1/admin/workflow-center/statistics
GET /api/v1/admin/workflow-center/health
GET /api/v1/admin/workflow-center/search
```

Protected definition management API:

```text
POST /api/v1/admin/workflow-center/definitions
PATCH /api/v1/admin/workflow-center/definitions/{definition_id}
POST /api/v1/admin/workflow-center/definitions/{definition_id}/versions
POST /api/v1/admin/workflow-center/definitions/{definition_id}/publish
POST /api/v1/admin/workflow-center/definitions/{definition_id}/deactivate
POST /api/v1/admin/workflow-center/definitions/{definition_id}/states
PATCH /api/v1/admin/workflow-center/definitions/{definition_id}/states/{state_id}
POST /api/v1/admin/workflow-center/definitions/{definition_id}/transitions
PATCH /api/v1/admin/workflow-center/definitions/{definition_id}/transitions/{transition_id}
POST /api/v1/admin/workflow-center/definitions/{definition_id}/sla
PATCH /api/v1/admin/workflow-center/definitions/{definition_id}/sla/{sla_id}
```

State-changing endpoints require CSRF and workflow management permissions.

## Permissions

- `workflows.view`
- `workflows.manage`
- `workflows.publish`
- `workflows.instances.view`
- `workflows.instances.transition`
- `workflows.sla.view`
- `workflows.sla.manage`

Workflow Center uses these existing permissions and does not introduce a separate authorization model.

## Workflow Center

The UI is available at `/admin/workflow-center` and includes:

- dashboard and global search;
- definition catalog and definition detail;
- read-only process diagram;
- validation center;
- version list and version diff;
- instance explorer and instance detail timeline;
- SLA center;
- outbox monitor without raw payload exposure;
- process audit;
- platform health summary backed by Platform Doctor.

## Future Extension Points

The schema and service boundaries keep room for future capabilities:

- multiple workflow-enabled modules;
- multiple definitions per module;
- parallel workflows for the same entity through `instance_key`;
- sub-workflows through `parent_instance_id`;
- scheduled transitions;
- event-driven transitions;
- external integrations;
- BPMN-like execution.

These capabilities are not implemented in Phase 3.

## Diagnostics

Run Platform Doctor before startup and after upgrades:

```bash
cd backend
uv run python -m app.scripts.platform_doctor
```

If the doctor reports partial workflow migration state, start with:

```bash
uv run python -m app.scripts.recover_partial_workflow_migration --dry-run
```
