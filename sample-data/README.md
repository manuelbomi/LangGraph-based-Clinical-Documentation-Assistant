# Sample data

**Everything in this folder is entirely synthetic and fictitious.** The
patients ("Avery Kim", "Riley Thompson"), the clinic/hospital ("Cedar
Hollow Family Health Clinic", "Cedar Hollow Medical Center"), the
providers ("Priya Anand, MD", "Marcus Delgado, MD"), the MRNs, dates, and
all clinical details (symptoms, vitals, medications, diagnoses) were
invented for this repository. **No real patient, no real clinician, and
no real medical record was used or referenced in any way.**

This app is an **administrative documentation assistant, not a diagnostic
or clinical-decision-support tool.** It never suggests diagnoses,
treatments, or medical advice -- it only summarizes and structures
information a (fictitious, in this demo) clinician has already written,
and every output must be reviewed and approved by a clinician before it
is considered final. See the root `README.md` "Scope & Safety" section.

## What's here

### `notes/` -- 5 synthetic clinical notes (plain text)

Plain `.txt` files (the ingest node also supports `.pdf`, extracted with
`pdfplumber`, for a real uploaded discharge summary PDF -- the bundled
samples are plain text purely for readability/diffability in a git repo).
Each varies in complexity, matching the tutorial's requirement to exercise
a simple note, a complex multi-diagnosis discharge summary, a medication
change, and a note with follow-up/referral instructions:

| File | Patient | Complexity | Notable |
|---|---|---|---|
| `outpatient_pharyngitis_avery_kim.txt` | Avery Kim | Simple, single problem | Acute pharyngitis, new antibiotic |
| `hypertension_med_change_avery_kim.txt` | Avery Kim | Medication change | Lisinopril -> losartan (ACE-inhibitor cough) |
| `discharge_chf_multidx_riley_thompson.txt` | Riley Thompson | Complex, multi-diagnosis | Heart failure exacerbation discharge; 4 problems, 6 medications |
| `low_back_pain_referral_riley_thompson.txt` | Riley Thompson | Follow-up / referral | Physical therapy referral |
| `chronic_disease_mgmt_avery_kim.txt` | Avery Kim | Chronic disease management | Hyperlipidemia, prediabetes, obesity |

Three of these (`outpatient_pharyngitis_avery_kim`,
`hypertension_med_change_avery_kim`, `discharge_chf_multidx_riley_thompson`)
are pre-processed and seeded into the database (see `organizer`/seed
scripts below) so the "Patient Encounter History" page has real example
analyses out of the box. The remaining two are available in the app's
"run a bundled sample" picker for a live, zero-setup demo of the full
graph (including the clinician review step) without needing to upload
your own file.

### `icd10/icd10_reference.csv` -- a small curated ICD-10-CM reference subset

33 real, publicly-published ICD-10-CM codes and their official short
descriptions (a tiny hand-picked subset relevant to the conditions
mentioned in the sample notes above -- e.g. hypertension, heart failure,
type 2 diabetes, hyperlipidemia, low back pain, acute pharyngitis). This
is public government reference data (the ICD-10-CM code set is published
by the CDC/NCHS), not clinical advice or a complete code set.

The app embeds this CSV into a local Milvus Lite collection at startup
(see `backend/app/tools/icd10_lookup.py`) and uses semantic (embedding)
search to suggest the closest-matching code(s) for each free-text problem
description the `extract_structured` node pulled from a note. Suggestions
are always labeled "for clinician confirmation" and are never
auto-applied to a patient's record -- see the root README's Scope &
Safety section.

### `patients/` -- 2 fictitious patient records (JSON)

Loaded into the `patients` table by `backend/scripts/seed_patients.py`.
Each is a minimal fictitious identity (name, MRN, date of birth) with no
real-world correspondence.

## Regenerating / extending

There's nothing to "generate" here (unlike the PDF-heavy sibling tutorial
that recreates IRS forms with `reportlab`) -- these are hand-authored
plain-text notes and a hand-curated public reference CSV. To add another
sample note, drop a new `.txt`/`.pdf` file in `notes/`, add an entry to
`SAMPLE_CATALOG` in `backend/app/api/routers/encounters.py`, and
optionally add a pre-baked example via `backend/scripts/seed_examples.py`.
