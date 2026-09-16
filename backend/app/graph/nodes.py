"""LangGraph node implementations for the Clinical Documentation & Discharge
Summary Assistant.

Six real (non-stub) nodes, wired as a straight line (no conditional
routing -- every note goes through the same pipeline):

    ingest -> extract_structured -> code_lookup -> generate_patient_summary
    -> clinician_review -> finalize

  ingest                  - reads raw text from a .txt file or a .pdf's text
                            layer (pdfplumber)
  extract_structured      - LLM extracts a `StructuredClinicalNote`: chief
                            complaint, problem list, medications, allergies,
                            follow-up/referrals, vitals -- constrained to
                            only structure what the clinician already wrote
  code_lookup             - deterministic (no LLM call): semantic search of
                            each problem-list item against a small curated
                            ICD-10 reference set (Milvus Lite), producing
                            SUGGESTED codes for clinician confirmation
  generate_patient_summary - LLM rewrites the structured data into a
                            plain-language after-visit summary
  clinician_review        - interrupt() pauses the graph for a clinician's
                            review/edit/approval -- the mandatory safety gate
  finalize                - records the clinician's decision

This app is strictly an administrative documentation assistant. It never
diagnoses, recommends treatment, or offers medical advice -- see the root
README's "Scope & Safety" section and the seeded prompt text in
`app/prompts/seed_prompts.py`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langgraph.types import interrupt

from app.graph.note_schema import StructuredClinicalNote
from app.graph.state import ClinicalIntakeState, ProblemCodeSuggestions, TraceEvent
from app.llm import get_chat_model
from app.prompts import render_prompt
from app.tools.document_ingest import detect_file_kind, extract_pdf_text, extract_text_file
from app.tools.icd10_lookup import search_icd10

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace(node: str, summary: str) -> list[TraceEvent]:
    return [{"node": node, "timestamp": _now(), "summary": summary}]


# --------------------------------------------------------------------------
# 1. ingest
# --------------------------------------------------------------------------
async def ingest_node(state: ClinicalIntakeState) -> dict:
    file_path = state["file_path"]
    kind = detect_file_kind(file_path)

    if kind == "pdf":
        raw_text = extract_pdf_text(file_path)
        note = "" if len(raw_text) >= 40 else " (suspiciously little text extracted)"
        return {
            "raw_text": raw_text,
            "trace": _trace("ingest", f"Detected PDF; extracted {len(raw_text)} chars of text{note}."),
        }

    raw_text = extract_text_file(file_path)
    return {
        "raw_text": raw_text,
        "trace": _trace("ingest", f"Detected plain-text note; read {len(raw_text)} chars."),
    }


# --------------------------------------------------------------------------
# 2. extract_structured
# --------------------------------------------------------------------------
async def extract_structured_node(state: ClinicalIntakeState) -> dict:
    llm = get_chat_model()
    structured_llm = llm.with_structured_output(StructuredClinicalNote)

    try:
        prompt_text = render_prompt("extract_structured_note", raw_text=state.get("raw_text", ""))
        result = await structured_llm.ainvoke(prompt_text)
        structured_note = result.model_dump()
    except Exception as exc:  # noqa: BLE001
        logger.exception("extract_structured_node: extraction failed")
        return {
            "structured_note": StructuredClinicalNote().model_dump(),
            "trace": _trace(
                "extract_structured",
                f"Extraction failed ({exc.__class__.__name__}); left structured note empty.",
            ),
        }

    n_problems = len(structured_note.get("problem_list", []))
    n_meds = len(structured_note.get("medications", []))
    return {
        "structured_note": structured_note,
        "trace": _trace(
            "extract_structured", f"Extracted {n_problems} problem(s) and {n_meds} medication(s)."
        ),
    }


# --------------------------------------------------------------------------
# 3. code_lookup (deterministic wrt the LLM; real embedding search)
# --------------------------------------------------------------------------
async def code_lookup_node(state: ClinicalIntakeState) -> dict:
    structured_note = state.get("structured_note") or {}
    problems = structured_note.get("problem_list", [])

    suggestions: list[ProblemCodeSuggestions] = []
    for problem in problems:
        description = problem.get("description", "") if isinstance(problem, dict) else str(problem)
        if not description:
            continue
        hits = search_icd10(description)
        suggestions.append(
            {
                "problem": description,
                "suggestions": [
                    {
                        "code": hit.code if hasattr(hit, "code") else hit["code"],
                        "description": hit.description if hasattr(hit, "description") else hit["description"],
                        "score": hit.score if hasattr(hit, "score") else hit["score"],
                    }
                    for hit in hits
                ],
            }
        )

    return {
        "code_suggestions": suggestions,
        "trace": _trace(
            "code_lookup",
            f"Looked up suggested ICD-10 codes for {len(suggestions)} problem(s) (for clinician confirmation).",
        ),
    }


# --------------------------------------------------------------------------
# 4. generate_patient_summary
# --------------------------------------------------------------------------
async def generate_patient_summary_node(state: ClinicalIntakeState) -> dict:
    llm = get_chat_model()
    structured_note = state.get("structured_note") or {}

    try:
        prompt_text = render_prompt(
            "generate_patient_summary", structured_note_json=json.dumps(structured_note)
        )
        result = await llm.ainvoke(prompt_text)
        summary = result.content if hasattr(result, "content") else str(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_patient_summary_node: summary generation failed")
        summary = (
            "A plain-language summary could not be generated automatically for this visit. "
            "Please review the structured record above with your clinician."
        )
        return {
            "patient_summary": summary,
            "trace": _trace(
                "generate_patient_summary",
                f"Summary generation failed ({exc.__class__.__name__}); used fallback text.",
            ),
        }

    return {
        "patient_summary": summary,
        "trace": _trace("generate_patient_summary", f"Generated a {len(summary)}-character patient summary."),
    }


# --------------------------------------------------------------------------
# 5. clinician_review
# --------------------------------------------------------------------------
async def clinician_review_node(state: ClinicalIntakeState) -> dict:
    """Pause the graph and wait for a clinician's decision.

    `interrupt()` raises a `GraphInterrupt` the first time this node runs
    for a given thread; LangGraph's Postgres checkpointer persists state up
    to (but not including) this node's completion, so the process can exit
    entirely and be resumed later via `Command(resume=...)` against the
    same `thread_id` -- see `app/api/routers/encounters.py::resume_encounter`.

    This is the mandatory safety gate for the whole application: nothing
    produced by `extract_structured`/`code_lookup`/`generate_patient_summary`
    is part of a patient's record until a clinician explicitly approves,
    corrects, or rejects it here. A clinician typically works through a
    review queue asynchronously -- not necessarily right after a note is
    uploaded, sometimes hours or days later -- which is exactly why this
    graph needs a durable, Postgres-backed checkpointer rather than
    in-process state: the interrupt must survive a server restart just as
    easily as it survives the clinician simply closing their browser tab.
    """
    payload = interrupt(
        {
            "original_filename": state.get("original_filename"),
            "structured_note": state.get("structured_note", {}),
            "code_suggestions": state.get("code_suggestions", []),
            "patient_summary": state.get("patient_summary", ""),
        }
    )
    decision = str(payload.get("decision", "approve")).lower()
    feedback = str(payload.get("feedback", ""))
    corrected_structured_note = payload.get("corrected_structured_note")
    corrected_patient_summary = payload.get("corrected_patient_summary")
    accepted_codes = payload.get("accepted_codes") or {}
    if decision not in {"approve", "correct", "reject"}:
        decision = "approve"

    update: dict = {
        "human_decision": decision,
        "human_feedback": feedback,
        "accepted_codes": accepted_codes,
        "trace": _trace("clinician_review", f"Clinician decision={decision} | {feedback[:200]}"),
    }

    if decision == "correct":
        if corrected_structured_note:
            update["structured_note"] = corrected_structured_note
            update["corrected_structured_note"] = corrected_structured_note
        if corrected_patient_summary:
            update["patient_summary"] = corrected_patient_summary
            update["corrected_patient_summary"] = corrected_patient_summary

    return update


# --------------------------------------------------------------------------
# 6. finalize
# --------------------------------------------------------------------------
async def finalize_node(state: ClinicalIntakeState) -> dict:
    decision = state.get("human_decision", "approve")

    if decision == "reject":
        final_status, status = "rejected", "rejected"
        summary = "Encounter rejected by clinician; not added to the patient's record."
    else:
        final_status = "corrected_and_added" if decision == "correct" else "added_to_record"
        status = "completed"
        summary = f"Encounter finalized with status={final_status}."

    return {"final_status": final_status, "status": status, "trace": _trace("finalize", summary)}
