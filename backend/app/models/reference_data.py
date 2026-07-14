from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class City(TimestampMixin, Base):
    __tablename__ = "cities"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    facilities: Mapped[list["Facility"]] = relationship(back_populates="city")
    responsibilities: Mapped[list["ContractorResponsibility"]] = relationship(back_populates="city")


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    city_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    city: Mapped[City] = relationship(back_populates="facilities")
    premises: Mapped[list["Premise"]] = relationship(back_populates="facility")
    responsibilities: Mapped[list["ContractorResponsibility"]] = relationship(back_populates="facility")


class Premise(TimestampMixin, Base):
    __tablename__ = "premises"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facility_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("facilities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_access_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    facility: Mapped[Facility] = relationship(back_populates="premises")


class Contractor(TimestampMixin, Base):
    __tablename__ = "contractors"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    responsibilities: Mapped[list["ContractorResponsibility"]] = relationship(back_populates="contractor")


class WorkType(TimestampMixin, Base):
    __tablename__ = "work_types"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    requires_premise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    responsibilities: Mapped[list["ContractorResponsibility"]] = relationship(back_populates="work_type")


class ContractorResponsibility(TimestampMixin, Base):
    __tablename__ = "contractor_responsibilities"
    __table_args__ = (
        UniqueConstraint(
            "contractor_id",
            "city_id",
            "facility_id",
            "work_type_id",
            name="uq_contractor_responsibility_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    contractor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contractors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    city_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    facility_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("facilities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    work_type_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    contractor: Mapped[Contractor] = relationship(back_populates="responsibilities")
    city: Mapped[City | None] = relationship(back_populates="responsibilities")
    facility: Mapped[Facility | None] = relationship(back_populates="responsibilities")
    work_type: Mapped[WorkType] = relationship(back_populates="responsibilities")
