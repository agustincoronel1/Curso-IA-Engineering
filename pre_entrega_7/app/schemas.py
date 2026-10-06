"""Schemas Pydantic de la API."""

from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    DONE = "DONE"
    FAILED = "FAILED"


class TaskRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    estimated_cost: Optional[float] = Field(
        default=None, ge=0, description="Costo estimado; si >= HITL_COST_THRESHOLD exige aprobación."
    )


class TaskCreated(BaseModel):
    job_id: str
    status: JobStatus


class TaskStatus(BaseModel):
    job_id: str
    status: JobStatus
    input: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    approval_request: Optional[dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    approved: bool
    comment: Optional[str] = Field(default=None, max_length=500)
