from datetime import datetime, timezone

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="citizen")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    jurisdiction: Mapped[str] = mapped_column(String(255), default="")
    contact_information: Mapped[str] = mapped_column(String(255), default="")
    official_source_url: Mapped[str] = mapped_column(String(500), default="")
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    grievances: Mapped[list["Grievance"]] = relationship(back_populates="department")


class Grievance(Base):
    __tablename__ = "grievances"
    id: Mapped[int] = mapped_column(primary_key=True)
    grievance_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True))
    address: Mapped[str] = mapped_column(String(500), default="")
    severity: Mapped[str] = mapped_column(String(20), default="Medium", index=True)
    severity_score: Mapped[int] = mapped_column(Integer, default=0)
    severity_factors: Mapped[list] = mapped_column(JSONB, default=list)
    ai_analysis: Mapped[dict] = mapped_column(JSONB, default=dict)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Submitted", index=True)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("grievances.id"), nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    department: Mapped[Department | None] = relationship(back_populates="grievances")
    history: Mapped[list["GrievanceHistory"]] = relationship(back_populates="grievance", cascade="all, delete-orphan", order_by="GrievanceHistory.created_at")
    reports: Mapped[list["GrievanceReport"]] = relationship(back_populates="grievance", cascade="all, delete-orphan")
    duplicate_parent: Mapped["Grievance | None"] = relationship(remote_side=[id], foreign_keys=[duplicate_of])

    @property
    def department_name(self) -> str | None:
        return self.department.name if self.department else None


class GrievanceHistory(Base):
    __tablename__ = "grievance_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    grievance_id: Mapped[int] = mapped_column(ForeignKey("grievances.id"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    grievance: Mapped[Grievance] = relationship(back_populates="history")


class GrievanceReport(Base):
    __tablename__ = "grievance_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    grievance_id: Mapped[int] = mapped_column(ForeignKey("grievances.id"), index=True)
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    grievance: Mapped[Grievance] = relationship(back_populates="reports")
