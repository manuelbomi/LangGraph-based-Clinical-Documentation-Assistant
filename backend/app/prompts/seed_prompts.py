"""Seed version-1 prompts for the `extract_structured_node` and
`generate_patient_summary_node` graph nodes.

Run with:
    python -m app.prompts.seed_prompts

Safe to re-run: it only inserts a new version if the active template text
for a given name has actually changed.

Both templates open with the same safety framing sentence, which is the
single most important line in this entire repository: this assistant
structures and summarizes what a clinician already wrote -- it never
diagnoses, recommends treatment, or offers medical advice, and nothing it
produces is final until a clinician reviews and approves it.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Prompt
from app.db.session import SessionLocal
from app.prompts.registry import add_prompt_version

_SAFETY_FRAMING = (
    "You are a clinical documentation assistant. You summarize and structure "
    "existing clinician-authored notes. You do not diagnose, recommend "
    "treatment, or offer medical advice."
)

PROMPTS_V1: dict[str, str] = {
    "extract_structured_note": (
        f"{_SAFETY_FRAMING}\n\n"
        "Read the clinical note below and extract ONLY the following fields, "
        "exactly as they are stated in the note: the chief complaint; the "
        "problem list (each diagnosis/problem written in the clinician's own "
        "words, from the assessment or problem list section); medications "
        "(name, dose, frequency, and any qualifier such as 'new' or "
        "'discontinued', exactly as written); allergies; follow-up "
        "instructions and referrals; and vital signs, if present.\n\n"
        "If a piece of information is not present in the note, leave that "
        "field empty. Do not infer, guess, estimate, or add any diagnosis, "
        "medication, instruction, or vital sign that is not explicitly "
        "stated in the note text below. Do not rephrase a diagnosis into "
        "different or more specific medical terminology than the clinician "
        "used -- copy their wording for the problem list.\n\n"
        "Below is the clinician's note:\n\n-----\n{raw_text}\n-----"
    ),
    "generate_patient_summary": (
        f"{_SAFETY_FRAMING}\n\n"
        "Below is a structured record of a clinical encounter, extracted "
        "directly from the clinician's own note (as JSON). Rewrite it as a "
        "short, warm, plain-language after-visit summary the patient can "
        "understand -- write in the second person ('You came in for...', "
        "'Your medications are...'), expand medical jargon and abbreviations "
        "into everyday language, and organize it around what happened, what "
        "changed, and what to do next.\n\n"
        "Do not add any new clinical content: no new diagnosis, no new "
        "medication, no treatment recommendation, and no reassurance or "
        "advice that is not already present in the structured data below. "
        "Only rephrase and simplify what is already there. End the summary "
        "with one short sentence noting that this summary was reviewed by "
        "their clinician.\n\n"
        "Structured encounter data (JSON):\n\n-----\n{structured_note_json}\n-----"
    ),
}


def seed() -> None:
    with SessionLocal() as db:
        for name, template in PROMPTS_V1.items():
            active = db.execute(
                select(Prompt).where(Prompt.name == name, Prompt.is_active.is_(True))
            ).scalar_one_or_none()
            if active is not None and active.template == template:
                print(f"[skip] '{name}' already has this template active (v{active.version})")
                continue
            version = add_prompt_version(name, template, activate=True)
            print(f"[seeded] '{name}' -> v{version}")


if __name__ == "__main__":
    seed()
