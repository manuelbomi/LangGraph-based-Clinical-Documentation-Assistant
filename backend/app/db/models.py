"""SQLAlchemy models: the `prompts` registry, `patients` (fictitious
identities), and `encounters` (every clinical note ever processed for a
patient -- this doubles as both the "run history" and the durable, but
NOT-yet-final-until-reviewed, structured documentation record).

Note: LangGraph's `AsyncPostgresSaver` manages its own checkpoint tables
(`checkpoints`, `checkpoint_writes`, ...) via `checkpointer.setup()` -- those
are NOT modeled here and are intentionally left out of Alembic's autogenerate
scope (see `db/migrations/env.py`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Prompt(Base):
    """A versioned prompt template.

    Only one version per `name` is `is_active` at a time; `get_prompt(name)`
    (see `app/prompts/registry.py`) resolves to that active version. There
    are exactly two prompts in this app: `extract_structured_note` and
    `generate_patient_summary`.
    """

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Prompt name={self.name!r} v{self.version} active={self.is_active}>"


class Patient(Base):
    """One fictitious demo patient (see `sample-data/README.md` -- entirely
    synthetic identities, never real patient data)."""

    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mrn: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    date_of_birth: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    encounters: Mapped[list["Encounter"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", order_by="Encounter.created_at"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Patient name={self.name!r} mrn={self.mrn!r}>"


class Encounter(Base):
    """One end-to-end clinical documentation run, keyed by the LangGraph
    `thread_id`. Every note a patient's encounter ever produces gets a row
    here -- this is both the "run history" for the frontend and the durable
    documentation record `finalize_node` writes to.

    Nothing in `structured_note` / `code_suggestions` / `patient_summary` is
    considered part of the patient's actual record until a clinician has
    reviewed it via the `clinician_review` interrupt and this row's
    `final_status` reflects that decision -- see the root README's
    "Scope & Safety" section.
    """

    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    patient_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # pending | running | awaiting_human | completed | rejected | error
    final_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # added_to_record | corrected_and_added | rejected

    structured_note: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    code_suggestions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    accepted_codes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    patient_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient: Mapped[Patient] = relationship(back_populates="encounters")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Encounter id={self.id} patient_id={self.patient_id!r} status={self.status!r}>"
