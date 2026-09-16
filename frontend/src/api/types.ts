/**
 * Hand-written TypeScript mirror of `backend/app/api/schemas.py`.
 * Keep these two files in sync when the API contract changes.
 */

export type EncounterStatus = "pending" | "running" | "awaiting_human" | "completed" | "rejected" | "error";

export interface PatientSummary {
  id: string;
  name: string;
  mrn: string;
  date_of_birth: string;
}

export interface EncounterSummary {
  id: string;
  patient_id: string;
  original_filename: string;
  status: EncounterStatus;
  final_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatientDetail extends PatientSummary {
  notes: string;
  encounters: EncounterSummary[];
}

export interface PatientListResponse {
  patients: PatientSummary[];
}

export interface SampleDocument {
  id: string;
  label: string;
  suggested_patient_id: string | null;
}

export interface SamplesResponse {
  samples: SampleDocument[];
}

export interface EncounterCreateResponse {
  id: string;
  patient_id: string;
  status: EncounterStatus;
  original_filename: string;
}

export interface MedicationItem {
  name: string;
  dosage: string;
  frequency: string;
  notes: string;
}

export interface ProblemItem {
  description: string;
}

export interface VitalSigns {
  blood_pressure: string;
  heart_rate: string;
  temperature: string;
  respiratory_rate: string;
  oxygen_saturation: string;
  weight: string;
  height: string;
}

export function emptyVitals(): VitalSigns {
  return {
    blood_pressure: "",
    heart_rate: "",
    temperature: "",
    respiratory_rate: "",
    oxygen_saturation: "",
    weight: "",
    height: "",
  };
}

export interface StructuredClinicalNote {
  chief_complaint: string;
  problem_list: ProblemItem[];
  medications: MedicationItem[];
  allergies: string[];
  follow_up_instructions: string[];
  referrals: string[];
  vitals: VitalSigns;
}

export function emptyStructuredNote(): StructuredClinicalNote {
  return {
    chief_complaint: "",
    problem_list: [],
    medications: [],
    allergies: [],
    follow_up_instructions: [],
    referrals: [],
    vitals: emptyVitals(),
  };
}

export interface SuggestedICD10Code {
  code: string;
  description: string;
  score: number;
}

export interface ProblemCodeSuggestions {
  problem: string;
  suggestions: SuggestedICD10Code[];
}

export interface HumanDecisionRequest {
  decision: "approve" | "correct" | "reject";
  feedback: string;
  corrected_structured_note?: StructuredClinicalNote | null;
  corrected_patient_summary?: string | null;
  accepted_codes?: Record<string, string | null> | null;
}

export interface TraceEventOut {
  node: string;
  timestamp: string;
  summary: string;
}

export interface EncounterDetail extends EncounterSummary {
  structured_note: StructuredClinicalNote;
  code_suggestions: ProblemCodeSuggestions[];
  accepted_codes: Record<string, string | null>;
  patient_summary: string;
  trace: TraceEventOut[];
  state_snapshot: Record<string, unknown>;
  error: string | null;
}

export interface EncounterListResponse {
  encounters: EncounterSummary[];
}

/** Payload of the `interrupt` SSE event -- what `clinician_review_node` pauses with. */
export interface InterruptPayload {
  original_filename: string;
  structured_note: StructuredClinicalNote;
  code_suggestions: ProblemCodeSuggestions[];
  patient_summary: string;
}

/** Shapes of the SSE events emitted by GET /encounters/{id}/stream. */
export type StreamEvent =
  | { type: "node"; node: string; output: Record<string, unknown>; trace: TraceEventOut[] }
  | { type: "interrupt"; data: InterruptPayload }
  | { type: "done"; status: EncounterStatus; final_status: string | null }
  | { type: "error"; message: string }
  | {
      type: "replay";
      status: EncounterStatus;
      trace: TraceEventOut[];
      state_snapshot: Record<string, unknown>;
      final_status: string | null;
    };

/** The graph node names, in the order they appear in the LangGraph
 * StateGraph (backend/app/graph/graph.py). This graph is linear -- every
 * encounter visits all six nodes in this exact order, unlike the
 * conditional-routing graphs in other tutorials in this series. */
export const GRAPH_NODES = [
  "ingest",
  "extract_structured",
  "code_lookup",
  "generate_patient_summary",
  "clinician_review",
  "finalize",
] as const;

export type GraphNodeName = (typeof GRAPH_NODES)[number];

export const GRAPH_NODE_LABELS: Record<GraphNodeName, string> = {
  ingest: "Ingest",
  extract_structured: "Extract Structured Note",
  code_lookup: "ICD-10 Code Lookup",
  generate_patient_summary: "Generate Patient Summary",
  clinician_review: "Clinician Review",
  finalize: "Finalize",
};
