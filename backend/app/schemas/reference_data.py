from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CityBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="City name.")
    code: str = Field(min_length=1, max_length=64, description="Unique city code.")
    is_active: bool = Field(default=True, description="Whether the city can be used.")


class CityCreate(CityBase):
    pass


class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None


class CityResponse(CityBase, ReferenceResponse):
    pass


class FacilityBase(BaseModel):
    city_id: UUID = Field(description="Parent city identifier.")
    name: str = Field(min_length=1, max_length=255, description="Facility name.")
    address: str = Field(min_length=1, max_length=500, description="Facility address.")
    code: str = Field(min_length=1, max_length=64, description="Unique facility code.")
    is_active: bool = Field(default=True, description="Whether the facility can be used.")


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    city_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None


class FacilityResponse(FacilityBase, ReferenceResponse):
    pass


class PremiseBase(BaseModel):
    facility_id: UUID = Field(description="Parent facility identifier.")
    name: str = Field(min_length=1, max_length=255, description="Premise name.")
    number: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=128)
    owner_name: str | None = Field(default=None, max_length=255)
    owner_email: str | None = Field(default=None, max_length=255)
    owner_phone: str | None = Field(default=None, max_length=64)
    has_access_control: bool = Field(default=False, description="Whether the premise has access control.")
    is_active: bool = Field(default=True, description="Whether the premise can be used.")


class PremiseCreate(PremiseBase):
    pass


class PremiseUpdate(BaseModel):
    facility_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    number: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=128)
    owner_name: str | None = Field(default=None, max_length=255)
    owner_email: str | None = Field(default=None, max_length=255)
    owner_phone: str | None = Field(default=None, max_length=64)
    has_access_control: bool | None = None
    is_active: bool | None = None


class PremiseResponse(PremiseBase, ReferenceResponse):
    pass


class ContractorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Contractor organization name.")
    code: str = Field(min_length=1, max_length=64, description="Unique contractor code.")
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    is_active: bool = Field(default=True, description="Whether the contractor can be used.")


class ContractorCreate(ContractorBase):
    pass


class ContractorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class ContractorResponse(ContractorBase, ReferenceResponse):
    pass


class WorkTypeBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Work type name.")
    code: str = Field(min_length=1, max_length=64, description="Unique work type code.")
    requires_premise: bool = Field(default=False, description="Whether a premise is required.")
    is_active: bool = Field(default=True, description="Whether the work type can be used.")


class WorkTypeCreate(WorkTypeBase):
    pass


class WorkTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    requires_premise: bool | None = None
    is_active: bool | None = None


class WorkTypeResponse(WorkTypeBase, ReferenceResponse):
    pass


class ContractorResponsibilityBase(BaseModel):
    contractor_id: UUID = Field(description="Contractor identifier.")
    city_id: UUID | None = Field(default=None, description="Optional city scope.")
    facility_id: UUID | None = Field(default=None, description="Optional facility scope.")
    work_type_id: UUID = Field(description="Work type identifier.")
    priority: int = Field(default=100, ge=0, description="Lower values have higher priority.")
    is_active: bool = Field(default=True, description="Whether the responsibility can be used.")


class ContractorResponsibilityCreate(ContractorResponsibilityBase):
    pass


class ContractorResponsibilityUpdate(BaseModel):
    contractor_id: UUID | None = None
    city_id: UUID | None = None
    facility_id: UUID | None = None
    work_type_id: UUID | None = None
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ContractorResponsibilityResponse(ContractorResponsibilityBase, ReferenceResponse):
    pass
