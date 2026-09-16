"""Real (non-stub) note ingestion helpers: plain-text reading and PDF text
extraction.

Unlike `langgraph-tutorial-03`'s scanned tax forms, this app's clinical
notes are typed documents (EHR exports, dictated-and-transcribed discharge
summaries) -- there is no scanned/photographed input to fall back to a
vision LLM for, so `ingest_node` only needs two deterministic paths: read a
`.txt` file directly, or extract a `.pdf`'s text layer with `pdfplumber`
(pure Python, no native/system dependency, works identically on Windows,
macOS, Linux, and inside the Docker image).
"""
from __future__ import annotations

import os

TEXT_EXTENSIONS = {".txt"}
PDF_EXTENSIONS = {".pdf"}


def detect_file_kind(file_path: str) -> str:
    """Classify a file purely from its extension: "text" or "pdf"."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    raise ValueError(
        f"Unsupported file extension {ext!r}. Supported: {sorted(TEXT_EXTENSIONS | PDF_EXTENSIONS)}"
    )


def extract_text_file(file_path: str) -> str:
    with open(file_path, encoding="utf-8") as f:
        return f.read().strip()


def extract_pdf_text(file_path: str) -> str:
    """Extract all text from a PDF using `pdfplumber`."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    return "\n".join(parts).strip()
