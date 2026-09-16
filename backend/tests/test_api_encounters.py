"""API contract tests for the /patients and /encounters endpoints.

Uses a lightweight in-memory fake in place of the Postgres-backed
`SessionLocal`, and an `InMemorySaver` in place of the Postgres checkpointer,
so these run without any real database. LLM + ICD-10 lookup calls are
mocked exactly as in `test_graph_nodes.py` / `test_graph_flow.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver

from app.api.routers.encounters import router as encounters_router
from app.api.routers.patients import router as patients_router
from app.config import Settings
from app.db.models import Encounter, Patient
from app.graph.graph import build_graph
from app.graph.note_schema import StructuredClinicalNote


class _FakeResultSet:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, patients: dict, encounters: dict):
        self._patients = patients
        self._encounters = encounters

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, obj) -> None:
        if isinstance(obj, Patient):
            self._patients[obj.id] = obj
        elif isinstance(obj, Encounter):
            self._encounters[obj.id] = obj

    def commit(self) -> None:
        pass

    def get(self, model, id_):
        if model is Patient:
            return self._patients.get(id_)
        if model is Encounter:
            return self._encounters.get(id_)
        return None

    def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Patient:
            rows = sorted(self._patients.values(), key=lambda p: p.name)
        else:
            rows = sorted(self._encounters.values(), key=lambda e: e.created_at, reverse=True)
        return _FakeResultSet(rows)


def _seed_patient(patients: dict, patient_id="avery-kim") -> Patient:
    patient = Patient(
        id=patient_id,
        name="Avery Kim",
        mrn="MRN-100482",
        date_of_birth="1987-04-12",
        notes="",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    patients[patient_id] = patient
    return patient


@pytest.fixture
def api_app(monkeypatch, fake_chat_model, fake_prompts, no_icd10_io, tmp_path):
    patients: dict[str, Patient] = {}
    encounters: dict[str, Encounter] = {}
    _seed_patient(patients)

    monkeypatch.setattr("app.api.routers.patients.SessionLocal", lambda: _FakeSession(patients, encounters))
    monkeypatch.setattr("app.api.routers.encounters.SessionLocal", lambda: _FakeSession(patients, encounters))

    fake_settings = Settings(
        upload_dir=str(tmp_path / "uploads"), sample_data_dir=str(tmp_path / "sample-data")
    )
    monkeypatch.setattr("app.api.routers.encounters.get_settings", lambda: fake_settings)

    monkeypatch.setattr("app.graph.nodes.extract_text_file", lambda p: "sore throat, 3 days")
    monkeypatch.setattr("app.graph.nodes.extract_pdf_text", lambda p: "sore throat, 3 days")

    app = FastAPI()
    app.state.run_queues = {}
    app.state.run_tasks = {}
    app.state.graph = build_graph(checkpointer=InMemorySaver())
    app.include_router(patients_router)
    app.include_router(encounters_router)
    return app, patients, encounters


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _extraction_and_summary_responses() -> list:
    return [
        StructuredClinicalNote(
            chief_complaint="Sore throat for 3 days.",
            problem_list=[{"description": "Acute pharyngitis, likely streptococcal."}],
        ),
        "You have strep throat and were started on an antibiotic.",
    ]


async def test_list_patients_returns_seeded_patient(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.get("/patients")
        assert resp.status_code == 200
        ids = {p["id"] for p in resp.json()["patients"]}
        assert "avery-kim" in ids


async def test_get_patient_detail(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.get("/patients/avery-kim")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Avery Kim"


async def test_get_unknown_patient_404(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.get("/patients/does-not-exist")
        assert resp.status_code == 404


async def test_list_samples_returns_catalog(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.get("/encounters/samples")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()["samples"]}
        assert "pharyngitis-avery-kim" in ids


async def test_upload_note_reaches_clinician_review(api_app, fake_chat_model):
    app, _, _ = api_app
    fake_chat_model(_extraction_and_summary_responses())

    async with await _client(app) as client:
        resp = await client.post(
            "/encounters/upload",
            data={"patient_id": "avery-kim"},
            files={"file": ("note.txt", b"Chief complaint: sore throat.", "text/plain")},
        )
        assert resp.status_code == 200
        enc_id = resp.json()["id"]

        await app.state.run_tasks[enc_id]

        detail = await client.get(f"/encounters/{enc_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["status"] == "awaiting_human"
        assert body["structured_note"]["chief_complaint"] == "Sore throat for 3 days."
        assert len(body["trace"]) >= 3


async def test_upload_unknown_patient_404(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.post(
            "/encounters/upload",
            data={"patient_id": "does-not-exist"},
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 404


async def test_upload_rejects_unsupported_extension(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.post(
            "/encounters/upload",
            data={"patient_id": "avery-kim"},
            files={"file": ("note.docx", b"hello", "application/octet-stream")},
        )
        assert resp.status_code == 400


async def test_run_sample_note(api_app, fake_chat_model, tmp_path):
    app, _, _ = api_app
    fake_chat_model(_extraction_and_summary_responses())

    sample_dir = tmp_path / "sample-data" / "notes"
    sample_dir.mkdir(parents=True)
    (sample_dir / "outpatient_pharyngitis_avery_kim.txt").write_text("Chief complaint: sore throat.")

    async with await _client(app) as client:
        resp = await client.post("/encounters/samples/pharyngitis-avery-kim/run", data={"patient_id": "avery-kim"})
        assert resp.status_code == 200
        enc_id = resp.json()["id"]

        await app.state.run_tasks[enc_id]

        detail = await client.get(f"/encounters/{enc_id}")
        assert detail.json()["structured_note"]["chief_complaint"] == "Sore throat for 3 days."


async def test_run_unknown_sample_404(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.post("/encounters/samples/does-not-exist/run", data={"patient_id": "avery-kim"})
        assert resp.status_code == 404


async def test_resume_encounter_completes(api_app, fake_chat_model):
    app, _, _ = api_app
    fake_chat_model(_extraction_and_summary_responses())

    async with await _client(app) as client:
        resp = await client.post(
            "/encounters/upload",
            data={"patient_id": "avery-kim"},
            files={"file": ("note.txt", b"Chief complaint: sore throat.", "text/plain")},
        )
        enc_id = resp.json()["id"]
        await app.state.run_tasks[enc_id]

        resume_resp = await client.post(
            f"/encounters/{enc_id}/resume", json={"decision": "approve", "feedback": "Looks good."}
        )
        assert resume_resp.status_code == 200
        await app.state.run_tasks[enc_id]

        detail = await client.get(f"/encounters/{enc_id}")
        body = detail.json()
        assert body["status"] == "completed"
        assert body["final_status"] == "added_to_record"


async def test_resume_rejects_when_not_found(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.post(
            "/encounters/does-not-exist/resume", json={"decision": "approve", "feedback": ""}
        )
        assert resp.status_code == 404


async def test_list_encounters_returns_summaries(api_app):
    app, _, encounters = api_app
    now = datetime.now(timezone.utc)
    encounters["e1"] = Encounter(
        id="e1", patient_id="avery-kim", original_filename="a.txt", status="completed",
        final_status="added_to_record", structured_note={}, code_suggestions=[], accepted_codes={},
        patient_summary="", trace=[], state_snapshot={}, created_at=now, updated_at=now,
    )
    encounters["e2"] = Encounter(
        id="e2", patient_id="avery-kim", original_filename="b.txt", status="awaiting_human",
        final_status=None, structured_note={}, code_suggestions=[], accepted_codes={},
        patient_summary="", trace=[], state_snapshot={}, created_at=now, updated_at=now,
    )

    async with await _client(app) as client:
        resp = await client.get("/encounters")
        assert resp.status_code == 200
        ids = {e["id"] for e in resp.json()["encounters"]}
        assert ids == {"e1", "e2"}


async def test_get_unknown_encounter_404(api_app):
    app, _, _ = api_app
    async with await _client(app) as client:
        resp = await client.get("/encounters/nope")
        assert resp.status_code == 404
