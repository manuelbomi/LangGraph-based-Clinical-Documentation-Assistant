"""REST + SSE API for clinical encounters: upload, the bundled-sample-note
catalog (for a zero-setup demo), starting/streaming/resuming an encounter's
graph run, and serving the original note back to the frontend detail view.

Concurrency model (intentionally simple for a tutorial app): each active
encounter run gets one `asyncio.Queue` in `request.app.state.run_queues`,
fed by a background `asyncio.Task` that drives `graph.astream(...)`. The
SSE endpoint just relays whatever lands on that queue. Every event is also
persisted to the `encounters` table as it happens, so a client that
reconnects (or a run that finished while nobody was watching) can still be
inspected via `GET /encounters/{id}` / replayed via
`GET /encounters/{id}/stream`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from langgraph.types import Command
from sqlalchemy import select

from app.api.schemas import (
    EncounterCreateResponse,
    EncounterDetail,
    EncounterListResponse,
    EncounterSummary,
    HumanDecisionRequest,
    SampleDocument,
    SamplesResponse,
)
from app.config import get_settings
from app.db.models import Encounter
from app.db.session import SessionLocal
from app.tools.document_ingest import detect_file_kind

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/encounters", tags=["encounters"])

_ALLOWED_EXTENSIONS = {".txt", ".pdf"}

# The catalog backing the "or pick one of the bundled sample notes"
# zero-setup demo path -- see sample-data/README.md for what each one is.
# `suggested_patient_id` is a hint the frontend uses to preselect a patient;
# any sample can be uploaded for any patient.
SAMPLE_CATALOG: list[dict[str, str]] = [
    {
        "id": "pharyngitis-avery-kim",
        "label": "Outpatient visit - Avery Kim - acute pharyngitis",
        "relative_path": "notes/outpatient_pharyngitis_avery_kim.txt",
        "suggested_patient_id": "avery-kim",
    },
    {
        "id": "htn-medchange-avery-kim",
        "label": "Outpatient visit - Avery Kim - hypertension medication change",
        "relative_path": "notes/hypertension_med_change_avery_kim.txt",
        "suggested_patient_id": "avery-kim",
    },
    {
        "id": "chf-discharge-riley-thompson",
        "label": "Hospital discharge - Riley Thompson - heart failure exacerbation (multi-diagnosis)",
        "relative_path": "notes/discharge_chf_multidx_riley_thompson.txt",
        "suggested_patient_id": "riley-thompson",
    },
    {
        "id": "low-back-pain-riley-thompson",
        "label": "Outpatient visit - Riley Thompson - low back pain with PT referral",
        "relative_path": "notes/low_back_pain_referral_riley_thompson.txt",
        "suggested_patient_id": "riley-thompson",
    },
    {
        "id": "chronic-disease-mgmt-avery-kim",
        "label": "Outpatient visit - Avery Kim - annual chronic disease management",
        "relative_path": "notes/chronic_disease_mgmt_avery_kim.txt",
        "suggested_patient_id": "avery-kim",
    },
]
_SAMPLE_BY_ID = {s["id"]: s for s in SAMPLE_CATALOG}


def _to_summary(encounter: Encounter) -> EncounterSummary:
    return EncounterSummary(
        id=encounter.id,
        patient_id=encounter.patient_id,
        original_filename=encounter.original_filename,
        status=encounter.status,  # type: ignore[arg-type]
        final_status=encounter.final_status,
        created_at=encounter.created_at,
        updated_at=encounter.updated_at,
    )


def _sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


async def _run_graph(request: Request, thread_id: str, graph_input: Any) -> None:
    """Background task: drive the graph, persist + broadcast each step."""
    graph = request.app.state.graph
    queue: asyncio.Queue = request.app.state.run_queues[thread_id]
    config = {"configurable": {"thread_id": thread_id}}

    def _set_status(status: str, **extra: Any) -> None:
        with SessionLocal() as db:
            enc = db.get(Encounter, thread_id)
            if enc is None:
                return
            enc.status = status
            for k, v in extra.items():
                setattr(enc, k, v)
            db.commit()

    def _record_event(node_output: dict[str, Any]) -> None:
        trace_items = node_output.get("trace", [])
        with SessionLocal() as db:
            enc = db.get(Encounter, thread_id)
            if enc is None:
                return
            enc.trace = [*enc.trace, *trace_items]
            merged_snapshot = {**enc.state_snapshot, **{k: v for k, v in node_output.items() if k != "trace"}}
            enc.state_snapshot = merged_snapshot
            if "structured_note" in node_output:
                enc.structured_note = node_output["structured_note"]
            if "code_suggestions" in node_output:
                enc.code_suggestions = node_output["code_suggestions"]
            if "patient_summary" in node_output:
                enc.patient_summary = node_output["patient_summary"]
            if "accepted_codes" in node_output:
                enc.accepted_codes = node_output["accepted_codes"]
            db.commit()

    try:
        _set_status("running")
        async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
            if "__interrupt__" in event:
                interrupt_obj = event["__interrupt__"][0]
                payload = dict(interrupt_obj.value)
                with SessionLocal() as db:
                    enc = db.get(Encounter, thread_id)
                    if enc is not None:
                        enc.status = "awaiting_human"
                        enc.state_snapshot = {**enc.state_snapshot, "interrupt": payload}
                        db.commit()
                await queue.put(_sse("interrupt", payload))
                continue

            for node_name, node_output in event.items():
                if not isinstance(node_output, dict):
                    continue
                _record_event(node_output)
                await queue.put(
                    _sse(
                        "node",
                        {
                            "node": node_name,
                            "output": {k: v for k, v in node_output.items() if k != "trace"},
                            "trace": node_output.get("trace", []),
                        },
                    )
                )
                if node_name != "clinician_review":
                    _set_status("running")

        # Loop ended without an interrupt -> graph ran to completion (END).
        state = await graph.aget_state(config)
        if not state.next:  # no pending nodes => finished
            values = state.values
            status = values.get("status", "completed")
            final_status = values.get("final_status")
            with SessionLocal() as db:
                enc = db.get(Encounter, thread_id)
                if enc is not None:
                    enc.status = status
                    enc.final_status = final_status
                    merged_snapshot = {**enc.state_snapshot, **values}
                    enc.state_snapshot = merged_snapshot
                    enc.structured_note = values.get("structured_note", enc.structured_note)
                    enc.code_suggestions = values.get("code_suggestions", enc.code_suggestions)
                    enc.patient_summary = values.get("patient_summary", enc.patient_summary)
                    enc.accepted_codes = values.get("accepted_codes", enc.accepted_codes)
                    db.commit()
            await queue.put(_sse("done", {"status": status, "final_status": final_status}))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Encounter run %s failed", thread_id)
        with SessionLocal() as db:
            enc = db.get(Encounter, thread_id)
            if enc is not None:
                enc.status = "error"
                enc.error = str(exc)
                db.commit()
        await queue.put(_sse("error", {"message": str(exc)}))
    finally:
        await queue.put(None)  # sentinel: close the SSE stream


def _start_background_run(request: Request, thread_id: str, graph_input: Any) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.run_queues[thread_id] = queue
    task = asyncio.create_task(_run_graph(request, thread_id, graph_input))
    request.app.state.run_tasks[thread_id] = task


async def start_encounter_run(
    request: Request,
    *,
    patient_id: str,
    file_path: str,
    original_filename: str,
    run_id: str | None = None,
) -> EncounterCreateResponse:
    """Create an `Encounter` row and kick off the graph in the background.
    Shared by both the upload and run-a-sample-note endpoints below."""
    with SessionLocal() as db:
        from app.db.models import Patient

        if db.get(Patient, patient_id) is None:
            raise HTTPException(404, f"patient {patient_id!r} not found")

    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        enc = Encounter(
            id=run_id,
            patient_id=patient_id,
            original_filename=original_filename,
            status="pending",
            structured_note={},
            code_suggestions=[],
            accepted_codes={},
            patient_summary="",
            trace=[],
            state_snapshot={},
            created_at=now,
            updated_at=now,
        )
        db.add(enc)
        db.commit()

    _start_background_run(
        request,
        run_id,
        {"file_path": file_path, "original_filename": original_filename, "patient_id": patient_id},
    )
    return EncounterCreateResponse(id=run_id, patient_id=patient_id, status="pending", original_filename=original_filename)


@router.get("/samples", response_model=SamplesResponse)
async def list_samples() -> SamplesResponse:
    return SamplesResponse(
        samples=[
            SampleDocument(id=s["id"], label=s["label"], suggested_patient_id=s["suggested_patient_id"])
            for s in SAMPLE_CATALOG
        ]
    )


@router.post("/samples/{sample_id}/run", response_model=EncounterCreateResponse)
async def run_sample_note(sample_id: str, request: Request, patient_id: str = Form(...)) -> EncounterCreateResponse:
    entry = _SAMPLE_BY_ID.get(sample_id)
    if entry is None:
        raise HTTPException(404, "unknown sample id")

    settings = get_settings()
    src_path = os.path.join(settings.sample_data_dir, entry["relative_path"])
    if not os.path.exists(src_path):
        raise HTTPException(500, f"sample file missing on server: {entry['relative_path']}")

    return await start_encounter_run(
        request,
        patient_id=patient_id,
        file_path=src_path,
        original_filename=os.path.basename(entry["relative_path"]),
    )


@router.post("/upload", response_model=EncounterCreateResponse)
async def upload_encounter(request: Request, patient_id: str = Form(...), file: UploadFile = File(...)) -> EncounterCreateResponse:
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type {ext or '(none)'!r}. Allowed: {sorted(_ALLOWED_EXTENSIONS)}")
    detect_file_kind(filename)  # raises if truly unrecognized

    settings = get_settings()
    run_id = str(uuid.uuid4())
    dest_dir = os.path.join(settings.upload_dir, run_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, filename)

    contents = await file.read()
    with open(dest_path, "wb") as f:
        f.write(contents)

    return await start_encounter_run(
        request, patient_id=patient_id, file_path=dest_path, original_filename=filename, run_id=run_id
    )


@router.get("/{encounter_id}/file")
async def get_encounter_source_file(encounter_id: str):
    """Serve the original uploaded/sample note back to the frontend, so the
    encounter detail view can show the source note alongside its structured
    record."""
    with SessionLocal() as db:
        enc = db.get(Encounter, encounter_id)
    if enc is None:
        raise HTTPException(404, "encounter not found")

    settings = get_settings()
    candidate = os.path.join(settings.upload_dir, encounter_id, enc.original_filename)
    if not os.path.exists(candidate):
        for sample in SAMPLE_CATALOG:
            if os.path.basename(sample["relative_path"]) == enc.original_filename:
                candidate = os.path.join(settings.sample_data_dir, sample["relative_path"])
                break

    if not os.path.exists(candidate):
        raise HTTPException(404, "original note not found on the server")

    return FileResponse(candidate, filename=enc.original_filename)


@router.post("/{encounter_id}/resume", response_model=EncounterCreateResponse)
async def resume_encounter(encounter_id: str, body: HumanDecisionRequest, request: Request) -> EncounterCreateResponse:
    with SessionLocal() as db:
        enc = db.get(Encounter, encounter_id)
        if enc is None:
            raise HTTPException(404, "encounter not found")
        if enc.status != "awaiting_human":
            raise HTTPException(409, f"encounter is not awaiting clinician review (status={enc.status})")
        patient_id = enc.patient_id
        original_filename = enc.original_filename

    _start_background_run(
        request,
        encounter_id,
        Command(
            resume={
                "decision": body.decision,
                "feedback": body.feedback,
                "corrected_structured_note": body.corrected_structured_note,
                "corrected_patient_summary": body.corrected_patient_summary,
                "accepted_codes": body.accepted_codes or {},
            }
        ),
    )
    return EncounterCreateResponse(
        id=encounter_id, patient_id=patient_id, status="running", original_filename=original_filename
    )


@router.get("/{encounter_id}/stream")
async def stream_encounter(encounter_id: str, request: Request) -> StreamingResponse:
    async def event_source():
        queue: asyncio.Queue | None = request.app.state.run_queues.get(encounter_id)

        if queue is None:
            # No live background task (already finished, or the server was
            # restarted after this encounter reached a terminal/awaiting
            # state). Replay what's durably stored instead of streaming live.
            with SessionLocal() as db:
                enc = db.get(Encounter, encounter_id)
            if enc is None:
                yield _sse("error", {"message": "encounter not found"})
                return
            yield _sse(
                "replay",
                {
                    "status": enc.status,
                    "trace": enc.trace,
                    "state_snapshot": enc.state_snapshot,
                    "final_status": enc.final_status,
                },
            )
            if enc.status == "awaiting_human":
                interrupt_payload = enc.state_snapshot.get("interrupt", {})
                yield _sse("interrupt", interrupt_payload)
            yield _sse("done", {"status": enc.status, "final_status": enc.final_status})
            return

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=EncounterListResponse)
async def list_encounters(patient_id: str | None = None) -> EncounterListResponse:
    with SessionLocal() as db:
        stmt = select(Encounter).order_by(Encounter.created_at.desc())
        if patient_id:
            stmt = stmt.where(Encounter.patient_id == patient_id)
        rows = db.execute(stmt).scalars().all()
        return EncounterListResponse(encounters=[_to_summary(e) for e in rows])


@router.get("/{encounter_id}", response_model=EncounterDetail)
async def get_encounter(encounter_id: str) -> EncounterDetail:
    with SessionLocal() as db:
        enc = db.get(Encounter, encounter_id)
        if enc is None:
            raise HTTPException(404, "encounter not found")
        return EncounterDetail(
            **_to_summary(enc).model_dump(),
            structured_note=enc.structured_note,
            code_suggestions=enc.code_suggestions,
            accepted_codes=enc.accepted_codes,
            patient_summary=enc.patient_summary,
            trace=enc.trace,
            state_snapshot=enc.state_snapshot,
            error=enc.error,
        )
