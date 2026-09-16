"""Unit tests for individual graph nodes.

Everything here is mocked: LLM calls go through `FakeChatModel` (see
conftest.py), and ICD-10 lookup I/O is monkeypatched via the `no_icd10_io`
fixture. No network, no Postgres, no Milvus, no API key spend.
"""
from __future__ import annotations

from app.graph import nodes
from app.graph.note_schema import StructuredClinicalNote


# ---------------------------------------------------------------------
# ingest_node
# ---------------------------------------------------------------------
async def test_ingest_node_text(monkeypatch):
    monkeypatch.setattr(nodes, "detect_file_kind", lambda p: "text")
    monkeypatch.setattr(nodes, "extract_text_file", lambda p: "Chief complaint: sore throat.")

    result = await nodes.ingest_node({"file_path": "note.txt"})

    assert result["raw_text"] == "Chief complaint: sore throat."
    assert len(result["trace"]) == 1


async def test_ingest_node_pdf(monkeypatch):
    monkeypatch.setattr(nodes, "detect_file_kind", lambda p: "pdf")
    monkeypatch.setattr(nodes, "extract_pdf_text", lambda p: "DISCHARGE SUMMARY " * 5)

    result = await nodes.ingest_node({"file_path": "note.pdf"})

    assert "raw_text" in result
    assert len(result["trace"]) == 1


# ---------------------------------------------------------------------
# extract_structured_node
# ---------------------------------------------------------------------
async def test_extract_structured_node_success(fake_chat_model, fake_prompts):
    note = StructuredClinicalNote(
        chief_complaint="Sore throat and low-grade fever for 3 days.",
        problem_list=[{"description": "Acute pharyngitis, likely streptococcal."}],
        medications=[{"name": "Amoxicillin", "dosage": "500 mg", "frequency": "twice daily"}],
    )
    fake_chat_model([note])

    result = await nodes.extract_structured_node({"raw_text": "some clinical note text"})

    assert result["structured_note"]["chief_complaint"] == "Sore throat and low-grade fever for 3 days."
    assert len(result["structured_note"]["problem_list"]) == 1
    assert result["trace"][0]["node"] == "extract_structured"


async def test_extract_structured_node_handles_failure(fake_chat_model, fake_prompts):
    fake_chat_model([RuntimeError("model refused")])

    result = await nodes.extract_structured_node({"raw_text": "garbled"})

    assert result["structured_note"] == StructuredClinicalNote().model_dump()
    assert "failed" in result["trace"][0]["summary"].lower()


# ---------------------------------------------------------------------
# code_lookup_node
# ---------------------------------------------------------------------
async def test_code_lookup_node_builds_suggestions(no_icd10_io):
    no_icd10_io.default_results = [
        {"code": "J02.9", "description": "Acute pharyngitis unspecified", "score": 0.91}
    ]

    result = await nodes.code_lookup_node(
        {"structured_note": {"problem_list": [{"description": "Acute pharyngitis"}]}}
    )

    assert len(result["code_suggestions"]) == 1
    assert result["code_suggestions"][0]["problem"] == "Acute pharyngitis"
    assert result["code_suggestions"][0]["suggestions"][0]["code"] == "J02.9"
    assert no_icd10_io.calls == ["Acute pharyngitis"]


async def test_code_lookup_node_empty_problem_list(no_icd10_io):
    result = await nodes.code_lookup_node({"structured_note": {"problem_list": []}})

    assert result["code_suggestions"] == []
    assert no_icd10_io.calls == []


# ---------------------------------------------------------------------
# generate_patient_summary_node
# ---------------------------------------------------------------------
async def test_generate_patient_summary_node_success(fake_chat_model, fake_prompts):
    fake_chat_model(["You came in with a sore throat and were started on an antibiotic."])

    result = await nodes.generate_patient_summary_node(
        {"structured_note": {"chief_complaint": "Sore throat"}}
    )

    assert "antibiotic" in result["patient_summary"]
    assert result["trace"][0]["node"] == "generate_patient_summary"


async def test_generate_patient_summary_node_handles_failure(fake_chat_model, fake_prompts):
    fake_chat_model([RuntimeError("model refused")])

    result = await nodes.generate_patient_summary_node({"structured_note": {}})

    assert "could not be generated" in result["patient_summary"]
    assert "failed" in result["trace"][0]["summary"].lower()


# ---------------------------------------------------------------------
# finalize_node
# ---------------------------------------------------------------------
async def test_finalize_node_approved():
    result = await nodes.finalize_node({"human_decision": "approve"})
    assert result["final_status"] == "added_to_record"
    assert result["status"] == "completed"


async def test_finalize_node_corrected():
    result = await nodes.finalize_node({"human_decision": "correct"})
    assert result["final_status"] == "corrected_and_added"
    assert result["status"] == "completed"


async def test_finalize_node_rejected():
    result = await nodes.finalize_node({"human_decision": "reject"})
    assert result["final_status"] == "rejected"
    assert result["status"] == "rejected"
