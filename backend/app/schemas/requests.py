from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.requests import AssignmentStatus, RequestStatus


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contractor_id: UUID
    work_type_id: UUID
    status: AssignmentStatus
    assigned_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContractorAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_type_id: UUID
    status: AssignmentStatus
    assigned_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None


class ContractorRequestBase(BaseModel):
    city_id: UUID = Field(description="City where the work is requested.")
    facility_id: UUID = Field(description="Facility where the work is requested.")
    premise_id: UUID | None = Field(default=None, description="Premise, required for work types that require it.")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=64)
    work_type_ids: list[UUID] = Field(min_length=1, description="One or more unique work type identifiers.")

    @field_validator("work_type_ids")
    @classmethod
    def validate_unique_work_types(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("work_type_ids must contain unique values")
        return value


class ContractorRequestCreate(ContractorRequestBase):
    pass


class ContractorRequestUpdate(BaseModel):
    city_id: UUID | None = None
    facility_id: UUID | None = None
    premise_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=64)
    work_type_ids: list[UUID] | None = Field(default=None, min_length=1)

    @field_validator("work_type_ids")
    @classmethod
    def validate_unique_work_types(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("work_type_ids must contain unique values")
        return value


class ContractorRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_number: str | None
    city_id: UUID
    facility_id: UUID
    premise_id: UUID | None
    title: str
    description: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    status: RequestStatus
    work_type_ids: list[UUID]
    assignments: list[AssignmentResponse]
    unassigned_work_type_ids: list[UUID] = []
    created_at: datetime
    updated_at: datetime


class ContractorRequestListResponse(BaseModel):
    id: UUID
    request_number: str | None
    city_id: UUID
    facility_id: UUID
    premise_id: UUID | None
    title: str
    status: RequestStatus
    work_type_ids: list[UUID]
    assignments: list[ContractorAssignmentResponse]
    created_at: datetime
    updated_at: datetime


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus = Field(description="New status for the contractor assignment.")


class RequestHistoryItem(BaseModel):
    event: str
    created_at: datetime
