"""End-to-end graph flow tests using LangGraph's in-memory checkpointer.

This proves the interrupt/resume *mechanics* (the same API the FastAPI app
uses against Postgres in `app/db/checkpointer.py`) without needing a real
database or LLM. The equivalent test against a *real* Postgres checkpointer
and a *real* OpenAI key lives in `tests/live/test_live_smoke.py`.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.graph import build_graph
from app.graph.note_schema import StructuredClinicalNote


async def test_note_pauses_at_clinician_review_and_resumes_to_completion(
    fake_chat_model, fake_prompts, no_icd10_io, monkeypatch
):
    monkeypatch.setattr("app.graph.nodes.detect_file_kind", lambda p: "text")
    monkeypatch.setattr("app.graph.nodes.extract_text_file", lambda p: "sore throat, 3 days")
    no_icd10_io.default_results = [
        {"code": "J02.9", "description": "Acute pharyngitis unspecified", "score": 0.91}
    ]

    fake_chat_model(
        [
            StructuredClinicalNote(
                chief_complaint="Sore throat for 3 days.",
                problem_list=[{"description": "Acute pharyngitis, likely streptococcal."}],
                medications=[{"name": "Amoxicillin", "dosage": "500 mg", "frequency": "twice daily"}],
            ),
            "You have strep throat and were started on an antibiotic.",
        ]
    )

    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test-thread-pharyngitis"}}

    result = None
    async for event in graph.astream(
        {"file_path": "note.txt", "original_filename": "note.txt", "patient_id": "avery-kim"},
        config=config,
        stream_mode="updates",
    ):
        result = event

    assert result is not None
    assert "__interrupt__" in result, "graph should pause at clinician_review"
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["structured_note"]["chief_complaint"] == "Sore throat for 3 days."
    assert interrupt_payload["code_suggestions"][0]["suggestions"][0]["code"] == "J02.9"
    assert "strep throat" in interrupt_payload["patient_summary"]

    state_before_resume = await graph.aget_state(config)
    assert state_before_resume.next == ("clinician_review",)

    final_event = None
    async for event in graph.astream(
        Command(resume={"decision": "approve", "feedback": "Looks correct."}),
        config=config,
        stream_mode="updates",
    ):
        final_event = event

    assert "finalize" in final_event
    final_state = await graph.aget_state(config)
    assert final_state.next == ()  # graph reached END
    assert final_state.values["status"] == "completed"
    assert final_state.values["final_status"] == "added_to_record"


async def test_correct_decision_replaces_structured_note_and_summary(
    fake_chat_model, fake_prompts, no_icd10_io, monkeypatch
):
    monkeypatch.setattr("app.graph.nodes.detect_file_kind", lambda p: "text")
    monkeypatch.setattr("app.graph.nodes.extract_text_file", lambda p: "hypertension follow-up")
    no_icd10_io.default_results = []

    fake_chat_model(
        [
            StructuredClinicalNote(
                chief_complaint="Hypertension follow-up.",
                problem_list=[{"description": "Hypertension, well controlled."}],
            ),
            "Your blood pressure is well controlled.",
        ]
    )

    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test-thread-correct"}}

    async for _ in graph.astream(
        {"file_path": "note.txt", "original_filename": "note.txt", "patient_id": "avery-kim"},
        config=config,
        stream_mode="updates",
    ):
        pass

    corrected_note = {
        "chief_complaint": "Hypertension follow-up; new cough.",
        "problem_list": [{"description": "Hypertension, discontinuing lisinopril due to cough."}],
        "medications": [],
        "allergies": [],
        "follow_up_instructions": [],
        "referrals": [],
        "vitals": {},
    }
    async for _ in graph.astream(
        Command(
            resume={
                "decision": "correct",
                "feedback": "Clarified reason for medication change.",
                "corrected_structured_note": corrected_note,
                "corrected_patient_summary": "Your lisinopril was stopped due to a cough side effect.",
            }
        ),
        config=config,
        stream_mode="updates",
    ):
        pass

    final_state = await graph.aget_state(config)
    assert final_state.values["structured_note"]["chief_complaint"] == "Hypertension follow-up; new cough."
    assert final_state.values["patient_summary"] == "Your lisinopril was stopped due to a cough side effect."
    assert final_state.values["final_status"] == "corrected_and_added"


async def test_reject_decision_does_not_add_to_record(fake_chat_model, fake_prompts, no_icd10_io, monkeypatch):
    monkeypatch.setattr("app.graph.nodes.detect_file_kind", lambda p: "text")
    monkeypatch.setattr("app.graph.nodes.extract_text_file", lambda p: "note text")
    no_icd10_io.default_results = []

    fake_chat_model(
        [
            StructuredClinicalNote(chief_complaint="Some complaint."),
            "Plain-language summary.",
        ]
    )

    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test-thread-reject"}}

    async for _ in graph.astream(
        {"file_path": "note.txt", "original_filename": "note.txt", "patient_id": "riley-thompson"},
        config=config,
        stream_mode="updates",
    ):
        pass

    async for _ in graph.astream(
        Command(resume={"decision": "reject", "feedback": "Wrong patient, rejecting."}),
        config=config,
        stream_mode="updates",
    ):
        pass

    final_state = await graph.aget_state(config)
    assert final_state.values["final_status"] == "rejected"
    assert final_state.values["status"] == "rejected"
