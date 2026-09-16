"""Graph state schema.

A `TypedDict` (LangGraph's preferred state shape) rather than a Pydantic
model, so partial node returns (`{"structured_note": {...}}`) merge cleanly
via LangGraph's default "last write wins per key" reducer. Only `trace`
accumulates (via an `operator.add` reducer) since every other field is
written exactly once per run (this graph is a straight line -- there are no
revision loops; a clinician's correction is applied inline in
`clinician_review_node`, not by looping back).

`structured_note` is kept as a single nested dict (a dumped
`StructuredClinicalNote`, see `note_schema.py`) rather than flattened into
top-level state keys, since a clinician's correction replaces the whole
structured object wholesale.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SuggestedICD10Code(TypedDict):
    code: str
    description: str
    score: float


class ProblemCodeSuggestions(TypedDict):
    problem: str
    suggestions: list[SuggestedICD10Code]


class TraceEvent(TypedDict):
    node: str
    timestamp: str
    summary: str


class ClinicalIntakeState(TypedDict, total=False):
    # --- input ---
    file_path: str
    original_filename: str
    patient_id: str

    # --- ingest ---
    raw_text: str

    # --- extract_structured ---
    structured_note: dict[str, Any]  # dumped StructuredClinicalNote

    # --- code_lookup (suggestions only, never auto-applied) ---
    code_suggestions: list[ProblemCodeSuggestions]

    # --- generate_patient_summary ---
    patient_summary: str

    # --- clinician_review (human-in-the-loop, the mandatory safety gate) ---
    human_decision: str  # "approve" | "correct" | "reject" | ""
    human_feedback: str
    corrected_structured_note: dict[str, Any]
    corrected_patient_summary: str
    accepted_codes: dict[str, str | None]  # problem description -> accepted ICD-10 code (or None)

    # --- finalize ---
    final_status: str  # "added_to_record" | "corrected_and_added" | "rejected"
    status: str  # mirrors app.db.models.Encounter.status

    # --- observability (appended to, not replaced) ---
    trace: Annotated[list[TraceEvent], operator.add]
