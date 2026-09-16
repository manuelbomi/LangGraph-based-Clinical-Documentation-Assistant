#!/usr/bin/env sh
set -e

echo "[entrypoint] running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] seeding prompt registry (v1 prompts, no-op if already active)..."
python -m app.prompts.seed_prompts

echo "[entrypoint] seeding ICD-10 reference codes into Milvus Lite (no-op if already seeded)..."
python -m app.tools.icd10_lookup || echo "[entrypoint] ICD-10 seeding skipped/failed (needs OPENAI_API_KEY) -- continuing"

echo "[entrypoint] loading fictitious patients..."
python -m scripts.seed_patients

echo "[entrypoint] seeding example encounters (no-op if already present)..."
python -m scripts.seed_examples

echo "[entrypoint] starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
