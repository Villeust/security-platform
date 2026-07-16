# ERD

This document reflects existing database entities found in the current codebase. Planned modules are not included in the ERD until their entities exist in code.

```mermaid
erDiagram
    City ||--o{ Facility : contains
    Facility ||--o{ Premise : contains
    City ||--o{ ContractorRequest : scopes
    Facility ||--o{ ContractorRequest : receives
    Premise ||--o{ ContractorRequest : optional_scope

    ContractorRequest ||--o{ RequestWorkType : includes
    WorkType ||--o{ RequestWorkType : selected_for

    ContractorRequest ||--o{ RequestAssignment : creates
    Contractor ||--o{ RequestAssignment : assigned_to
    WorkType ||--o{ RequestAssignment : covers

    Contractor ||--o{ ContractorUser : has
    Contractor ||--o{ ContractorResponsibility : owns
    City ||--o{ ContractorResponsibility : city_scope
    Facility ||--o{ ContractorResponsibility : facility_scope
    WorkType ||--o{ ContractorResponsibility : work_scope

    WorkflowDefinition ||--o{ WorkflowState : owns
    WorkflowDefinition ||--o{ WorkflowTransition : owns
    WorkflowDefinition ||--o{ WorkflowSlaPolicy : owns
    WorkflowDefinition ||--o{ WorkflowInstance : starts
    WorkflowState ||--o{ WorkflowTransition : from_state
    WorkflowState ||--o{ WorkflowTransition : to_state
    WorkflowState ||--o{ WorkflowInstance : current_state
    WorkflowInstance ||--o{ WorkflowTransitionExecution : logs
    WorkflowInstance ||--o{ WorkflowSlaTimer : tracks
    WorkflowSlaPolicy ||--o{ WorkflowSlaTimer : creates

    City {
        uuid id PK
        string name
        string code
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Facility {
        uuid id PK
        uuid city_id FK
        string name
        string address
        string code
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Premise {
        uuid id PK
        uuid facility_id FK
        string name
        string number
        string category
        string owner_name
        string owner_email
        string owner_phone
        boolean has_access_control
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Contractor {
        uuid id PK
        string name
        string code
        string email
        string phone
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    WorkType {
        uuid id PK
        string name
        string code
        boolean requires_premise
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    ContractorResponsibility {
        uuid id PK
        uuid contractor_id FK
        uuid city_id FK
        uuid facility_id FK
        uuid work_type_id FK
        int priority
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    ContractorRequest {
        uuid id PK
        string request_number
        uuid city_id FK
        uuid facility_id FK
        uuid premise_id FK
        string title
        text description
        string contact_name
        string contact_email
        string contact_phone
        enum status
        datetime created_at
        datetime updated_at
    }

    RequestWorkType {
        uuid request_id PK,FK
        uuid work_type_id PK,FK
    }

    RequestAssignment {
        uuid id PK
        uuid request_id FK
        uuid contractor_id FK
        uuid work_type_id FK
        enum status
        datetime assigned_at
        datetime accepted_at
        datetime completed_at
        datetime created_at
        datetime updated_at
    }

    ContractorUser {
        uuid id PK
        uuid user_id
        uuid contractor_id FK
        boolean is_active
        datetime created_at
    }

    WorkflowDefinition {
        uuid id PK
        string code
        string name
        string entity_type
        int version
        boolean is_active
        boolean is_published
        datetime published_at
    }

    WorkflowState {
        uuid id PK
        uuid workflow_definition_id FK
        string code
        string name
        enum state_type
        boolean is_initial
        boolean is_terminal
        boolean is_active
    }

    WorkflowTransition {
        uuid id PK
        uuid workflow_definition_id FK
        uuid from_state_id FK
        uuid to_state_id FK
        string code
        string name
        string permission_code
        boolean is_active
    }

    WorkflowInstance {
        uuid id PK
        uuid workflow_definition_id FK
        uuid current_state_id FK
        string entity_type
        uuid entity_id
        string instance_key
        int workflow_version
        int lock_version
        datetime started_at
        datetime completed_at
    }

    WorkflowTransitionExecution {
        uuid id PK
        uuid workflow_instance_id FK
        uuid transition_id FK
        uuid from_state_id FK
        uuid to_state_id FK
        enum actor_type
        uuid actor_id
        string correlation_id
        datetime created_at
    }

    WorkflowSlaPolicy {
        uuid id PK
        uuid workflow_definition_id FK
        uuid state_id FK
        uuid transition_id FK
        string code
        int duration_minutes
        boolean is_active
    }

    WorkflowSlaTimer {
        uuid id PK
        uuid workflow_instance_id FK
        uuid sla_policy_id FK
        datetime due_at
        enum status
    }

    DomainEventOutbox {
        uuid id PK
        string event_type
        string aggregate_type
        uuid aggregate_id
        enum status
        int attempts
        datetime created_at
    }
```

## Notes

- `RequestWorkType` is a real association table between requests and work types.
- `ContractorResponsibility` is used by the assignment logic to find the contractor responsible for a work type in a city or facility scope.
- `ContractorUser` links platform users to contractors; user identity storage is not represented here because a dedicated user entity is not present in the current codebase.
- Workflow tables are generic platform entities. Contractor Requests is one workflow-enabled module, but the workflow schema is not tied to request-only business logic.
- `DomainEventOutbox` stores event payloads for backend delivery; Workflow Center exposes only safe metadata, not raw payloads.
