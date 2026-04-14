"""SQLAlchemy ORM models for group_db."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Payer(Base):
    __tablename__ = "payers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Employer(Base):
    __tablename__ = "employers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    payer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)


class Subgroup(Base):
    __tablename__ = "subgroups"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    employer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)


class EmployerPlanVisibility(Base):
    __tablename__ = "employer_plan_visibility"

    employer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("employer_id", "plan_id", name="employer_plan_visibility_pk"),
    )
