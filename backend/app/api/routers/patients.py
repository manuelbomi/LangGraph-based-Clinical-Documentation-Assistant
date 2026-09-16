"""Read-only patient endpoints: the per-patient encounter history that
backs the "Patient Encounter History / Example Analyses" page."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas import EncounterSummary, PatientDetail, PatientListResponse, PatientSummary
from app.db.models import Patient
from app.db.session import SessionLocal

router = APIRouter(prefix="/patients", tags=["patients"])


def _to_summary(patient: Patient) -> PatientSummary:
    return PatientSummary(
        id=patient.id, name=patient.name, mrn=patient.mrn, date_of_birth=patient.date_of_birth
    )


@router.get("", response_model=PatientListResponse)
async def list_patients() -> PatientListResponse:
    with SessionLocal() as db:
        rows = db.execute(select(Patient).order_by(Patient.name)).scalars().all()
        return PatientListResponse(patients=[_to_summary(p) for p in rows])


@router.get("/{patient_id}", response_model=PatientDetail)
async def get_patient(patient_id: str) -> PatientDetail:
    with SessionLocal() as db:
        patient = db.get(Patient, patient_id)
        if patient is None:
            raise HTTPException(404, "patient not found")
        encounters = [
            EncounterSummary(
                id=e.id,
                patient_id=e.patient_id,
                original_filename=e.original_filename,
                status=e.status,  # type: ignore[arg-type]
                final_status=e.final_status,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in patient.encounters
        ]
        summary = _to_summary(patient)
        return PatientDetail(**summary.model_dump(), notes=patient.notes, encounters=encounters)
