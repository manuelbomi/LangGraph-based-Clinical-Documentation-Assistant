"""Assembles the LangGraph `StateGraph` for the Clinical Documentation &
Discharge Summary Assistant.

    START -> ingest -> extract_structured -> code_lookup
          -> generate_patient_summary -> clinician_review -> finalize -> END

Unlike `langgraph-tutorial-03`'s per-document-type branching, every clinical
note follows the same straight-line pipeline -- there's no classification
step, since the input is always "one clinician's note" rather than one of
several IRS form types. `clinician_review`'s `interrupt()` is the load-
bearing piece of control flow here -- see `app/graph/nodes.py::clinician_review_node`.
"""
from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    clinician_review_node,
    code_lookup_node,
    extract_structured_node,
    finalize_node,
    generate_patient_summary_node,
    ingest_node,
)
from app.graph.state import ClinicalIntakeState


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Build (and optionally compile-with-checkpointer) the clinical intake
    graph.

    Pass `checkpointer=None` to get an uncompiled-but-still-runnable graph
    with LangGraph's default in-memory checkpointing (handy for unit tests
    that don't need durability/interrupts across processes). Pass a real
    `AsyncPostgresSaver` in the FastAPI app for durable, resumable runs.
    """
    builder = StateGraph(ClinicalIntakeState)

    builder.add_node("ingest", ingest_node)
    builder.add_node("extract_structured", extract_structured_node)
    builder.add_node("code_lookup", code_lookup_node)
    builder.add_node("generate_patient_summary", generate_patient_summary_node)
    builder.add_node("clinician_review", clinician_review_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "extract_structured")
    builder.add_edge("extract_structured", "code_lookup")
    builder.add_edge("code_lookup", "generate_patient_summary")
    builder.add_edge("generate_patient_summary", "clinician_review")
    builder.add_edge("clinician_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
