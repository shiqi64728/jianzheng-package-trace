"""Pydantic request contracts for the MVP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    case_name: str = Field(default="匿名演示案例", min_length=1, max_length=120)
    notes: str = Field(default="", max_length=500)


class ApiError(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ReviewCreate(BaseModel):
    node_from: str = Field(min_length=2, max_length=16)
    node_to: str = Field(min_length=2, max_length=16)
    surface: str = Field(default="front", min_length=1, max_length=16)
    review_class: str = Field(min_length=3, max_length=32)
    review_status: str = Field(min_length=3, max_length=16)
    reviewer_alias: str = Field(min_length=3, max_length=32)
    review_note: str = Field(default="", max_length=500)
    supersedes_review_id: str | None = Field(default=None, max_length=80)


class WorkOrderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    assigned_alias: str | None = Field(default=None, max_length=32)
    actor_alias: str = Field(default="DEMO-OPERATOR", min_length=3, max_length=32)
    note: str = Field(default="", max_length=500)


class WorkOrderEventCreate(BaseModel):
    event_type: str = Field(min_length=3, max_length=32)
    actor_alias: str = Field(min_length=3, max_length=32)
    new_state: str | None = Field(default=None, max_length=32)
    assigned_alias: str | None = Field(default=None, max_length=32)
    note: str = Field(default="", max_length=500)
    evidence_request: str = Field(default="", max_length=500)
