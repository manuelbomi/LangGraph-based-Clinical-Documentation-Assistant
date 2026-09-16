"""Shared test fixtures.

All tests in `tests/` (excluding `tests/live/`) are fully mocked: no real
LLM calls, no real Postgres, no real network, no real Milvus Lite. This
keeps `pytest` free and fast to run in CI. The real end-to-end path is
exercised separately by `tests/live/test_live_smoke.py`, which is excluded
by default (see the `live` marker in `pyproject.toml`) and requires a real
`OPENAI_API_KEY` plus a reachable Postgres.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")


class _FakeMessage:
    """Stands in for a LangChain `AIMessage` -- just needs `.content`."""

    def __init__(self, content: str):
        self.content = content


class _FakeStructuredRunnable:
    """Stands in for `chat_model.with_structured_output(Schema)`."""

    def __init__(self, parent: "FakeChatModel"):
        self._parent = parent

    async def ainvoke(self, prompt: Any, *args: Any, **kwargs: Any) -> Any:
        return self._parent._pop()


class FakeChatModel:
    """Stand-in for a LangChain chat model, supporting both
    `.with_structured_output(Schema).ainvoke(...)` (used by
    `extract_structured_node`) and a direct `.ainvoke(...)` plain-text call
    (used by `generate_patient_summary_node`).

    Construct with a list of canned responses: a pydantic model instance
    for a structured-output call, a plain `str` for a direct `.ainvoke()`
    call (auto-wrapped in a `_FakeMessage` so `.content` works), or an
    `Exception` instance to simulate a failure. Each call pops the next
    response in order, regardless of which method was used -- tests queue
    responses in the exact order the graph will call the model
    (extract_structured, then generate_patient_summary).
    """

    def __init__(self, responses: list[Any]):
        self._responses = list(responses)
        self.calls: list[Any] = []

    def _pop(self) -> Any:
        self.calls.append(True)
        if not self._responses:
            raise AssertionError("FakeChatModel called more times than responses were queued")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def with_structured_output(self, schema: Any) -> _FakeStructuredRunnable:
        return _FakeStructuredRunnable(self)

    async def ainvoke(self, prompt: Any, *args: Any, **kwargs: Any) -> Any:
        item = self._pop()
        if isinstance(item, str):
            return _FakeMessage(item)
        return item


@pytest.fixture
def fake_chat_model(monkeypatch):
    """Patch `app.graph.nodes.get_chat_model` to return a FakeChatModel.

    Returns a factory: `make(responses=[...])` -> the FakeChatModel instance,
    so each test controls exactly what the "LLM" returns at each graph step.
    """
    holder: dict[str, FakeChatModel] = {}

    def make(responses: list[Any]) -> FakeChatModel:
        model = FakeChatModel(responses)
        holder["model"] = model
        return model

    def fake_get_chat_model(*args: Any, **kwargs: Any) -> FakeChatModel:
        return holder["model"]

    monkeypatch.setattr("app.graph.nodes.get_chat_model", fake_get_chat_model)
    return make


@pytest.fixture
def fake_prompts(monkeypatch):
    """Patch `app.graph.nodes.render_prompt` to a template-free passthrough.

    Node logic is what's under test here, not prompt wording (that's
    covered by the real templates in `app/prompts/seed_prompts.py`, which
    the live smoke test exercises against a real LLM). This just avoids
    requiring a Postgres-backed prompt registry in unit tests.
    """

    def fake_render_prompt(name: str, **kwargs: Any) -> str:
        return f"[[{name}]] {kwargs}"

    monkeypatch.setattr("app.graph.nodes.render_prompt", fake_render_prompt)


@pytest.fixture
def no_icd10_io(monkeypatch):
    """Patch out the real Milvus Lite ICD-10 lookup that graph nodes make,
    so unit/flow/API tests never need milvus_lite installed or a seeded
    collection. Returns a small namespace: set `default_results` (a list of
    dicts with `code`/`description`/`score`) for every query, or key
    `results_by_query` by the exact problem description string for
    per-problem control."""

    class _Fakes:
        default_results: list[dict] = []
        results_by_query: dict[str, list[dict]] = {}
        calls: list[str] = []

    fakes = _Fakes()

    def fake_search_icd10(query: str, top_k: int | None = None):
        fakes.calls.append(query)
        return fakes.results_by_query.get(query, fakes.default_results)

    monkeypatch.setattr("app.graph.nodes.search_icd10", fake_search_icd10)
    return fakes
