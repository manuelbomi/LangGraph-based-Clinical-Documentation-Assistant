"""REAL end-to-end smoke test: actual OpenAI API calls + a real Postgres.

This is deliberately excluded from the default `pytest` run (see the `live`
marker + `addopts` in `pyproject.toml`). Run it explicitly with:

    export OPENAI_API_KEY=sk-...
    export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/clinical_docs
    cd backend
    pytest -m live tests/live/test_live_smoke.py -v -s

What it proves, with no mocks anywhere in the graph/LLM/DB path:
  1. A real sample note (`sample-data/notes/outpatient_pharyngitis_avery_kim.txt`)
     is ingested, structured by a real `gpt-4o-mini` call, summarized into
     plain language by a second real `gpt-4o-mini` call, and reaches
     `clinician_review`, genuinely pausing there (`interrupt()`).
  2. The checkpointer can be torn down and a BRAND NEW `AsyncPostgresSaver`
     + freshly-compiled graph (standing in for "a new process", e.g. the
     clinician coming back to their review queue later) can resume that
     exact thread and finish the run (`finalize`), adding it to the
     patient's record.

Cost note: this makes exactly TWO small `gpt-4o-mini` calls (structured
extraction + patient summary) plus a handful of small
`text-embedding-3-small` calls (ICD-10 collection seeding, ~33 short
strings, one-time, plus one query embedding for this note's single
problem) -- cheap.

Platform note: `code_lookup`/ICD-10 search silently returns no suggestions
if `milvus_lite` isn't installed/importable (see
`app/tools/icd10_lookup.py`'s broad except clause), which is expected on
native Windows. This test does NOT hard-assert `code_suggestions` is
non-empty for that reason -- it only asserts on the LLM-derived fields.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

if sys.platform == "win32":
    # psycopg's async mode cannot run on Windows' default ProactorEventLoop;
    # it needs a selector-based loop. This only matters for local dev on
    # Windows -- the backend Docker image (and CI) run on Linux, where this
    # is a no-op. See: https://www.psycopg.org/psycopg3/docs/advanced/async.html
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from alembic import command
from alembic.config import Config
from langgraph.types import Command

from app.config import get_settings
from app.db.checkpointer import build_checkpointer
from app.graph.graph import build_graph
from app.prompts.seed_prompts import seed as seed_prompts
from app.tools.icd10_lookup import seed_icd10_codes
from scripts.seed_patients import seed as seed_patients

pytestmark = pytest.mark.live

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_migrations() -> None:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "app", "db", "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="module", autouse=True)
def _prepare_schema():
    assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY must be set for the live smoke test"
    assert os.environ.get("DATABASE_URL"), "DATABASE_URL must point at a real reachable Postgres"
    _run_migrations()
    seed_prompts()
    seed_patients()
    try:
        seed_icd10_codes()
    except Exception as exc:  # noqa: BLE001 - see module docstring platform note
        print(f"[live smoke] ICD-10 seeding skipped/failed ({exc.__class__.__name__}): {exc}")
    yield


async def test_live_pharyngitis_note_survives_checkpointer_restart_and_is_added_to_record():
    settings = get_settings()
    note_path = os.path.join(settings.sample_data_dir, "notes", "outpatient_pharyngitis_avery_kim.txt")
    assert os.path.exists(note_path), f"sample note not found at {note_path}"

    thread_id = "live-smoke-thread"
    config = {"configurable": {"thread_id": thread_id}}
    graph_input = {
        "file_path": note_path,
        "original_filename": "outpatient_pharyngitis_avery_kim.txt",
        "patient_id": "avery-kim",
    }

    # --- Phase 1: run until it pauses at clinician_review -----------------
    async with build_checkpointer() as checkpointer_1:
        graph_1 = build_graph(checkpointer=checkpointer_1)

        saw_interrupt = False
        async for event in graph_1.astream(graph_input, config=config, stream_mode="updates"):
            print("EVENT:", list(event.keys()))
            if "__interrupt__" in event:
                saw_interrupt = True
                payload = event["__interrupt__"][0].value
                print("\n--- STRUCTURED NOTE + PATIENT SUMMARY AT CLINICIAN_REVIEW ---")
                print("structured_note:", payload["structured_note"])
                print("code_suggestions:", payload["code_suggestions"])
                print("patient_summary:", payload["patient_summary"])
                assert payload["structured_note"]["chief_complaint"], "expected a non-empty chief complaint"
                assert payload["structured_note"]["problem_list"], "expected at least one problem"
                assert payload["patient_summary"], "expected a non-empty patient summary"
        assert saw_interrupt, "graph should have paused at clinician_review"

        state = await graph_1.aget_state(config)
        assert state.next == ("clinician_review",)
    # `async with` exits here -> checkpointer_1's connection pool is fully
    # closed, simulating the backend process shutting down.

    # --- Phase 2: brand new checkpointer + graph, standing in for a ----
    # --- freshly-started process, resumes the SAME thread_id -----------
    async with build_checkpointer() as checkpointer_2:
        graph_2 = build_graph(checkpointer=checkpointer_2)

        # Prove the state genuinely persisted in Postgres, not in memory.
        resumed_state = await graph_2.aget_state(config)
        assert resumed_state.next == ("clinician_review",)
        assert resumed_state.values["structured_note"]["chief_complaint"]

        finished = False
        async for event in graph_2.astream(
            Command(resume={"decision": "approve", "feedback": "Approved by live smoke test."}),
            config=config,
            stream_mode="updates",
        ):
            print("RESUME EVENT:", list(event.keys()))
            if "finalize" in event:
                finished = True

        assert finished, "graph should have reached finalize after resume"
        final_state = await graph_2.aget_state(config)
        assert final_state.next == ()
        assert final_state.values["status"] == "completed"
        assert final_state.values["final_status"] == "added_to_record"
        print("\n--- FINAL STATE ---\n", {"final_status": final_state.values["final_status"]})
