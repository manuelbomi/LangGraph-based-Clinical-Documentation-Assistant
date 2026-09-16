"""Load the bundled fictitious patient identities (`sample-data/patients/*.json`)
into the `patients` table.

Run with:
    python -m scripts.seed_patients

Safe to re-run: upserts by the patient `id` in each JSON file rather than
inserting duplicates.
"""
from __future__ import annotations

import glob
import json
import os

from app.config import get_settings
from app.db.models import Patient
from app.db.session import SessionLocal


def seed() -> None:
    settings = get_settings()
    patients_dir = os.path.join(settings.sample_data_dir, "patients")
    paths = sorted(glob.glob(os.path.join(patients_dir, "*.json")))
    if not paths:
        raise SystemExit(
            f"No patient records found in {patients_dir!r}. Did you set "
            "SAMPLE_DATA_DIR correctly?"
        )

    with SessionLocal() as db:
        for path in paths:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            patient = db.get(Patient, data["id"])
            if patient is None:
                patient = Patient(
                    id=data["id"],
                    name=data["name"],
                    mrn=data.get("mrn", ""),
                    date_of_birth=data.get("date_of_birth", ""),
                    notes=data.get("notes", ""),
                )
                db.add(patient)
                print(f"[seeded] patient {data['id']!r} ({data['name']})")
            else:
                patient.name = data["name"]
                patient.mrn = data.get("mrn", "")
                patient.date_of_birth = data.get("date_of_birth", "")
                patient.notes = data.get("notes", "")
                print(f"[updated] patient {data['id']!r} ({data['name']})")
        db.commit()


if __name__ == "__main__":
    seed()
