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
