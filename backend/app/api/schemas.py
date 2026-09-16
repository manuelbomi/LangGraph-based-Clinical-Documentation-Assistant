"""Pydantic request/response schemas for the REST + SSE API.

Keep these in sync with `frontend/src/api/types.ts` -- that file is a
hand-written TypeScript mirror of this one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

EncounterStatus = Literal["pending", "running", "awaiting_human", "completed", "rejected", "error"]


class PatientSummary(BaseModel):
    id: str
    name: str
    mrn: str
    date_of_birth: str


class PatientDetail(PatientSummary):
    notes: str
    encounters: list["EncounterSummary"]


class PatientListResponse(BaseModel):
    patients: list[PatientSummary]


class SampleDocument(BaseModel):
    id: str
    label: str
    suggested_patient_id: str | None = None


class SamplesResponse(BaseModel):
    samples: list[SampleDocument]


class EncounterCreateResponse(BaseModel):
    id: str
    patient_id: str
    status: EncounterStatus
    original_filename: str


class HumanDecisionRequest(BaseModel):
    decision: Literal["approve", "correct", "reject"]
    feedback: str = ""
    corrected_structured_note: dict[str, Any] | None = None
    corrected_patient_summary: str | None = None
    accepted_codes: dict[str, str | None] | None = None


class TraceEventOut(BaseModel):
    node: str
    timestamp: datetime
    summary: str


class EncounterSummary(BaseModel):
    id: str
    patient_id: str
    original_filename: str
    status: EncounterStatus
    final_status: str | None
    created_at: datetime
    updated_at: datetime


class EncounterDetail(EncounterSummary):
    structured_note: dict[str, Any]
    code_suggestions: list[dict[str, Any]]
    accepted_codes: dict[str, Any]
    patient_summary: str
    trace: list[TraceEventOut]
    state_snapshot: dict[str, Any]
    error: str | None


class EncounterListResponse(BaseModel):
    encounters: list[EncounterSummary]


PatientDetail.model_rebuild()
