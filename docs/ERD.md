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
```

## Notes

- `RequestWorkType` is a real association table between requests and work types.
- `ContractorResponsibility` is used by the assignment logic to find the contractor responsible for a work type in a city or facility scope.
- `ContractorUser` links platform users to contractors; user identity storage is not represented here because a dedicated user entity is not present in the current codebase.
