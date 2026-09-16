"""Embedded vector-store ICD-10 semantic lookup tool, backed by Milvus Lite.

Milvus Lite (`pymilvus[milvus_lite]`) runs the vector database in-process
against a local file -- no Docker, no server, no network hop. This mirrors
`langgraph-tutorial-01`'s knowledge-base pattern exactly, applied to a small
curated public ICD-10-CM reference subset (see
`sample-data/icd10/icd10_reference.csv` and `sample-data/README.md` for
provenance) instead of a fixed demo corpus.

IMPORTANT (platform note): Milvus Lite's native binary is published for
Linux and macOS only. It works out of the box inside this repo's Linux
backend Docker image / CI, but will fail to import on native Windows
Python -- run the backend via Docker or WSL on Windows.

IMPORTANT (safety note): the results of `search_icd10` are SUGGESTIONS ONLY,
always surfaced to the clinician as "suggested code -- confirm before use"
(see `clinician_review_node` and the frontend's review panel). They are
never written to a patient's record without an explicit accept in the
`accepted_codes` field of the clinician's review decision.
"""
from __future__ import annotations

import csv
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.llm import get_embeddings

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_client = None  # lazily-created MilvusClient singleton


@dataclass
class ICD10Result:
    code: str
    description: str
    score: float


def _get_client():
    """Lazily create (and cache) the Milvus Lite client.

    Lazy + cached so importing this module never requires milvus_lite to be
    installed (unit tests monkeypatch `search_icd10` directly and never call
    this), and so the file-backed client is opened at most once per process.
    """
    global _client
    with _client_lock:
        if _client is None:
            from pymilvus import MilvusClient

            settings = get_settings()
            db_path = Path(settings.milvus_lite_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _client = MilvusClient(str(db_path))
        return _client


def ensure_collection(dim: int = 1536) -> None:
    """Create the ICD-10 collection if it doesn't already exist."""
    settings = get_settings()
    client = _get_client()
    if not client.has_collection(settings.milvus_collection):
        client.create_collection(
            collection_name=settings.milvus_collection,
            dimension=dim,
            metric_type="COSINE",
            auto_id=False,
        )


def _read_icd10_csv() -> list[tuple[str, str]]:
    settings = get_settings()
    csv_path = os.path.join(settings.sample_data_dir, "icd10", "icd10_reference.csv")
    rows: list[tuple[str, str]] = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append((row["code"].strip(), row["description"].strip()))
    return rows


def seed_icd10_codes(force: bool = False) -> int:
    """Embed and upsert the curated ICD-10 reference subset into Milvus Lite.

    Returns the number of codes (re)inserted. No-op if the collection
    already has data, unless `force=True`.
    """
    settings = get_settings()
    client = _get_client()

    if client.has_collection(settings.milvus_collection) and not force:
        stats = client.get_collection_stats(settings.milvus_collection)
        if int(stats.get("row_count", 0)) > 0:
            logger.info("ICD-10 collection already seeded (%s rows); skipping.", stats["row_count"])
            return 0

    codes = _read_icd10_csv()
    if not codes:
        raise SystemExit(
            f"No ICD-10 rows found under {settings.sample_data_dir!r}/icd10/icd10_reference.csv"
        )

    embeddings = get_embeddings()
    texts = [f"{code}: {description}" for code, description in codes]
    vectors = embeddings.embed_documents(texts)

    ensure_collection(dim=len(vectors[0]))

    rows = [
        {
            "id": idx,
            "vector": vector,
            "code": code,
            "description": description,
        }
        for idx, ((code, description), vector) in enumerate(zip(codes, vectors, strict=True))
    ]
    client.insert(collection_name=settings.milvus_collection, data=rows)
    logger.info("Seeded %d ICD-10 codes into Milvus Lite.", len(rows))
    return len(rows)


def search_icd10(query: str, top_k: int | None = None) -> list[ICD10Result]:
    """Embed `query` (a free-text problem description) and return the
    top-k closest-matching ICD-10 codes.

    Returns [] on any failure (e.g. collection not yet seeded, or -- on
    native Windows -- milvus_lite not being installed at all) so the graph
    degrades gracefully to "no suggestions" rather than crashing; the
    clinician can still code the encounter manually during review.
    """
    settings = get_settings()
    k = top_k or settings.icd10_top_k
    try:
        client = _get_client()
        if not client.has_collection(settings.milvus_collection):
            logger.warning("ICD-10 collection does not exist yet; returning no suggestions.")
            return []

        embeddings = get_embeddings()
        query_vector = embeddings.embed_query(query)

        hits = client.search(
            collection_name=settings.milvus_collection,
            data=[query_vector],
            limit=k,
            output_fields=["code", "description"],
        )
        results: list[ICD10Result] = []
        for hit in hits[0]:
            entity = hit.get("entity", hit)
            results.append(
                ICD10Result(
                    code=entity.get("code", ""),
                    description=entity.get("description", ""),
                    score=float(hit.get("distance", 0.0)),
                )
            )
        return results
    except Exception:  # noqa: BLE001 - deliberate, see docstring
        logger.exception("ICD-10 search failed for query=%r", query)
        return []


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-embed and re-insert even if already seeded.")
    args = parser.parse_args()
    inserted = seed_icd10_codes(force=args.force)
    print(f"Inserted {inserted} ICD-10 codes into Milvus Lite.")
