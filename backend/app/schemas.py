from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    previous_status: str | None
    new_status: str
    remarks: str
    created_at: datetime


class GrievanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grievance_number: str
    category: str
    description: str
    image_url: str | None
    latitude: float
    longitude: float
    address: str
    severity: str
    severity_score: int
    severity_factors: list[str]
    ai_analysis: dict[str, Any]
    processing_error: str | None
    status: str
    report_count: int
    duplicate_of: int | None
    department_name: str | None = None
    history: list[HistoryOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StatusUpdate(BaseModel):
    status: str
    remarks: str = Field(default="", max_length=1000)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    jurisdiction: str = Field(default="", max_length=255)
    contact_information: str = Field(default="", max_length=255)
    official_source_url: str = Field(default="", max_length=500)
    verification_status: str = Field(default="unverified", max_length=30)


class DepartmentOut(DepartmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
