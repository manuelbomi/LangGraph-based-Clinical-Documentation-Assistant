"""Pydantic schema used for LLM structured-output extraction of a clinical
note (`extract_structured_node`, `app/graph/nodes.py`).

This schema is deliberately narrow: every field only ever holds information
that was already written in the clinician's note. There is no "diagnosis",
"treatment_recommendation", or "clinical_impression" field the model could
use to introduce content of its own -- `problem_list` holds the clinician's
own diagnosis/assessment wording verbatim (or lightly paraphrased), never an
LLM-generated differential, and `follow_up_instructions`/`referrals` mirror
what the clinician already documented, not new advice. This mirrors the
"you do not diagnose, recommend treatment, or offer medical advice"
constraint from the seeded `extract_structured_note` prompt
(`app/prompts/seed_prompts.py`) at the type level, not just in prose.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MedicationItem(BaseModel):
    name: str = Field(description="Medication name, exactly as written in the note.")
    dosage: str = Field(default="", description="Dose, e.g. '500 mg'. Empty if not stated.")
    frequency: str = Field(default="", description="Frequency/route, e.g. 'twice daily by mouth'.")
    notes: str = Field(
        default="", description="Any qualifier the clinician wrote (e.g. 'new', 'discontinued', 'unchanged')."
    )


class ProblemItem(BaseModel):
    description: str = Field(
        description=(
            "One diagnosis/problem exactly as the clinician described it in the note's "
            "assessment/problem list -- never an LLM-inferred diagnosis."
        )
    )


class VitalSigns(BaseModel):
    """All optional -- only populate a field if that vital sign is explicitly stated in the note."""

    blood_pressure: str = Field(default="", description="e.g. '118/76'.")
    heart_rate: str = Field(default="", description="e.g. '88'.")
    temperature: str = Field(default="", description="e.g. '100.4 F'.")
    respiratory_rate: str = Field(default="", description="e.g. '16'.")
    oxygen_saturation: str = Field(default="", description="e.g. '98%'.")
    weight: str = Field(default="", description="e.g. '168 lb'.")
    height: str = Field(default="", description="e.g. '67 in'.")


class StructuredClinicalNote(BaseModel):
    chief_complaint: str = Field(default="", description="The chief complaint, as stated in the note.")
    problem_list: list[ProblemItem] = Field(default_factory=list)
    medications: list[MedicationItem] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list, description="Allergies exactly as listed in the note.")
    follow_up_instructions: list[str] = Field(
        default_factory=list, description="Follow-up instructions exactly as the clinician wrote them."
    )
    referrals: list[str] = Field(default_factory=list, description="Referrals exactly as documented in the note.")
    vitals: VitalSigns = Field(default_factory=VitalSigns)
