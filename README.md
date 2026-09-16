# LangGraph Tutorial 04: Clinical Documentation & Discharge Summary Assistant

A [LangGraph](https://langchain-ai.github.io/langgraph/)-powered assistant that
turns a clinician's free-text visit/discharge note into (1) a structured,
standardized record (problem list, medications, allergies, follow-up
instructions, suggested ICD-10 codes) and (2) a plain-language after-visit
summary a patient can actually understand -- both currently manual,
repetitive, and time-consuming tasks that are a major driver of clinician
"pajama time" and documentation burnout.

This is part of a tutorial series building small, production-shaped
LangGraph applications:

1. `langgraph-tutorial-01-research-report-assistant`
2. `langgraph-tutorial-02-invoice-audit-reconciliation`
3. `langgraph-tutorial-03-tax-document-intake`
4. **`langgraph-tutorial-04-clinical-documentation-assistant`** (this repo)

---

## Scope & Safety -- read this first

**This application is strictly an administrative documentation assistant. It
is NOT a diagnostic tool and NOT clinical-decision support.**

- It never suggests a diagnosis, recommends a treatment, or offers medical
  advice of any kind.
- It only summarizes, structures, and rephrases information a licensed
  clinician has **already written** in their own note. The extraction prompt
  is explicitly constrained to structure only what is stated in the note --
  never to infer, guess, or add new clinical content.
- ICD-10 codes are **suggested** via semantic similarity search for the
  clinician's confirmation only -- they are computed from the problem
  descriptions already in the note and are **never auto-applied** to a
  patient's record.
- **Every output (the structured record, the suggested codes, and the
  patient summary) must be explicitly reviewed and approved by a clinician**
  via the mandatory `clinician_review` step before it is considered final.
  Nothing is written to a patient's record without that explicit approval,
  correction, or rejection.
- **All data in this repository is entirely synthetic and fictitious.**
  There is no real patient, no real clinician, no real facility, and no real
  protected health information (PHI) anywhere in this repo. See
  `sample-data/README.md` for exactly what was invented and why.

This system prompt language is embedded directly in the seeded LLM prompts
(see `backend/app/prompts/seed_prompts.py`):

> "You are a clinical documentation assistant. You summarize and structure
> existing clinician-authored notes. You do not diagnose, recommend
> treatment, or offer medical advice."

The frontend also displays a persistent "not medical advice, clinician
review required" banner on every page, not just the review screen.

---

## What the app does

```mermaid
flowchart TD
    START([Upload / select note]) --> INGEST[ingest\nextract raw text from PDF/TXT]
    INGEST --> EXTRACT[extract_structured\nLLM: chief complaint, problem list,\nmedications, allergies, follow-up, vitals]
    EXTRACT --> CODE[code_lookup\nsemantic search vs. ICD-10 reference\nMilvus Lite embeddings]
    CODE --> SUMMARY[generate_patient_summary\nLLM: plain-language after-visit summary]
    SUMMARY --> REVIEW{{clinician_review\ninterrupt -- SAFETY GATE}}
    REVIEW -->|approve / correct / reject| FINALIZE[finalize\npersist clinician-approved record]
    FINALIZE --> END([Encounter recorded])

    style REVIEW fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

Six real graph nodes, run per encounter (one LangGraph thread per note):

1. **ingest** -- accepts an uploaded note (`.pdf` via `pdfplumber`, or
   `.txt`), extracts raw text.
2. **extract_structured** -- an LLM call (`gpt-4o-mini` by default)
   structures the note into a pydantic schema: chief complaint, problem
   list (free-text diagnosis descriptions **as the clinician wrote them**,
   never invented), medications (name/dose/frequency), allergies, follow-up
   instructions/referrals, vitals if present. The prompt explicitly forbids
   inferring or adding content not stated in the note.
3. **code_lookup** -- for each problem-list item, a semantic (embedding)
   search against a small curated ICD-10-CM reference set (embedded into a
   local **Milvus Lite** collection, no server/Docker container needed)
   suggests the closest-matching code(s), labeled "suggested -- for
   clinician confirmation."
4. **generate_patient_summary** -- a second LLM call rewrites the
   already-structured data into a plain-language after-visit summary, again
   constrained to rephrase/simplify only what's already present.
5. **clinician_review** (LangGraph `interrupt()`) -- **the mandatory safety
   gate.** Presents the structured record, suggested codes, and patient
   summary for the clinician to edit and Approve / Correct & Approve /
   Reject. Nothing is finalized without this step.
6. **finalize** -- records the clinician-approved (or corrected, or
   rejected) structured note and patient summary in Postgres.

---

## Why LangGraph specifically: durable checkpointing + mandatory human review

A real clinician's review queue doesn't get worked through in one sitting --
notes trickle in throughout the day, and a clinician may not open a given
encounter for review until hours or even days later, in between patients,
after clinic hours, or the next morning. **Nothing here should ever be
auto-finalized into a clinical record.** LangGraph's `interrupt()` combined
with the Postgres-backed checkpointer (`AsyncPostgresSaver`) is exactly the
right fit:

- Every encounter's graph run pauses durably at `clinician_review` -- the
  full state (raw text, structured note, suggested codes, generated summary)
  is persisted to Postgres, not held in server memory.
- The FastAPI process can restart, redeploy, or the encounter can simply sit
  untouched in a clinician's queue for as long as needed. When they come
  back (even from an entirely new process), `Command(resume=...)` against
  the same `thread_id` picks up exactly where it left off.
- This is proven end-to-end by `backend/tests/live/test_live_smoke.py`,
  which tears down and rebuilds the checkpointer + graph between the
  interrupt and the resume, simulating a clinician returning to their queue
  in a fresh process.

This mirrors the same durable-human-in-the-loop pattern used in
`langgraph-tutorial-03-tax-document-intake` (a preparer's document review
queue spanning all of tax season), applied here to a clinical documentation
workflow where the correctness bar for what enters the record is even
higher.

---

## Sample data / zero-setup demo

Everything needed for a working out-of-the-box demo is bundled and
entirely synthetic -- see `sample-data/README.md` for full provenance:

- `sample-data/notes/` -- 5 synthetic clinical notes (plain text): a simple
  single-problem outpatient visit, a note with a medication change, a
  complex multi-diagnosis hospital discharge summary, a note with a
  physical-therapy referral, and a chronic-disease-management visit.
- `sample-data/icd10/icd10_reference.csv` -- 33 real, publicly-published
  ICD-10-CM codes and descriptions (public reference data), used to seed the
  Milvus Lite semantic lookup.
- `sample-data/patients/` -- 2 fictitious patients (Avery Kim, Riley
  Thompson), each with prior processed example encounters already seeded
  into Postgres so the "Patient Encounter History" page has real content
  before you upload anything.

On first boot (`docker-entrypoint.sh`, or the manual steps below), the
backend runs migrations, seeds the two LLM prompts, embeds the ICD-10
reference set into Milvus Lite, loads the two fictitious patients, and
seeds 3 already-processed example encounters. You can then either upload
your own `.pdf`/`.txt` note, or run one of the two remaining bundled sample
notes end-to-end (including the live clinician-review step) straight from
the "Upload & Process" page.

---

## Repo structure

```
langgraph-tutorial-04-clinical-documentation-assistant/
├── backend/            FastAPI + LangGraph app (Python 3.11+)
│   ├── app/
│   │   ├── api/        REST + SSE routers (patients, encounters)
│   │   ├── db/         SQLAlchemy models, session, Postgres checkpointer, Alembic migrations
│   │   ├── graph/       LangGraph state, pydantic extraction schema, nodes, graph assembly
│   │   ├── prompts/     Postgres-backed prompt registry + v1 seed prompts
│   │   └── tools/       Note ingestion (PDF/TXT) + Milvus Lite ICD-10 semantic lookup
│   ├── scripts/         seed_patients.py, seed_examples.py
│   └── tests/           Mocked unit/flow/API tests + tests/live/ (real OpenAI + Postgres)
├── frontend/           Vite + React 18 + TypeScript + Tailwind
│   └── src/
│       ├── api/         Typed API client (mirrors backend/app/api/schemas.py)
│       ├── components/  GraphView (reactflow), ReviewForm (human-in-the-loop), output cards
│       ├── hooks/        useEncounterStream (SSE)
│       └── pages/        Upload & Process, Patient Encounter History, Encounter Detail
├── sample-data/        Synthetic notes, ICD-10 reference CSV, fictitious patients
├── docker-compose.yml  postgres + backend + frontend (Milvus Lite is embedded, no extra container)
└── .github/workflows/ci.yml
```

---

## Prompt registry

Both LLM prompts (`extract_structured_note`, `generate_patient_summary`)
live in the Postgres `prompts` table, versioned, with exactly one
`is_active` version per name at a time (`backend/app/prompts/registry.py`).
Seed or roll a new version with:

```bash
cd backend
python -m app.prompts.seed_prompts
```

or call `app.prompts.registry.add_prompt_version(name, new_template)` to
add and activate a new version programmatically (e.g. from a script or an
admin-only route) without redeploying code.

---

## Setup & run

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env   # fill in OPENAI_API_KEY
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000 (docs at `/docs`)
- Postgres: localhost:5432

Milvus Lite is **embedded** (a local file under the backend's `/app/data`
volume) -- there is no separate Milvus container, matching the pattern used
for the knowledge base in `langgraph-tutorial-01-research-report-assistant`.

### Option B: Local dev (no Docker)

Requires a local/reachable Postgres. **Note:** `pymilvus[milvus_lite]`'s
native binary is published for Linux/macOS only -- on native Windows,
`code_lookup` will gracefully degrade to "no suggested codes" (it catches
the import/connection failure and returns an empty list) rather than
crashing; run the backend via Docker or WSL on Windows if you need working
ICD-10 suggestions locally.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env   # edit as needed; also copy to backend/.env if you prefer per-service env files
alembic upgrade head
python -m app.prompts.seed_prompts
python -m app.tools.icd10_lookup   # embeds sample-data/icd10/icd10_reference.csv into Milvus Lite
python -m scripts.seed_patients
python -m scripts.seed_examples
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

### Running tests

```bash
# Backend -- mocked unit/flow/API tests (no real API calls, no live Postgres)
cd backend && pytest -v

# Backend -- REAL end-to-end smoke test (real OpenAI calls + real Postgres)
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/clinical_docs
pytest -m live tests/live/test_live_smoke.py -v -s

# Frontend
cd frontend
npm run typecheck
npm run build
npm run test
```

---

## License

MIT License, Copyright (c) 2026 Emmanuel Oyekanlu. See [`LICENSE`](./LICENSE).
