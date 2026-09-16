import type {
  EncounterCreateResponse,
  EncounterDetail,
  EncounterListResponse,
  HumanDecisionRequest,
  PatientDetail,
  PatientListResponse,
  SamplesResponse,
} from "./types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

export async function listPatients(): Promise<PatientListResponse> {
  const res = await fetch(`${API_BASE_URL}/patients`);
  return handle<PatientListResponse>(res);
}

export async function getPatient(patientId: string): Promise<PatientDetail> {
  const res = await fetch(`${API_BASE_URL}/patients/${encodeURIComponent(patientId)}`);
  return handle<PatientDetail>(res);
}

export async function listSamples(): Promise<SamplesResponse> {
  const res = await fetch(`${API_BASE_URL}/encounters/samples`);
  return handle<SamplesResponse>(res);
}

export async function runSampleDocument(sampleId: string, patientId: string): Promise<EncounterCreateResponse> {
  const formData = new FormData();
  formData.append("patient_id", patientId);
  const res = await fetch(`${API_BASE_URL}/encounters/samples/${encodeURIComponent(sampleId)}/run`, {
    method: "POST",
    body: formData,
  });
  return handle<EncounterCreateResponse>(res);
}

export async function uploadEncounter(file: File, patientId: string): Promise<EncounterCreateResponse> {
  const formData = new FormData();
  formData.append("patient_id", patientId);
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/encounters/upload`, { method: "POST", body: formData });
  return handle<EncounterCreateResponse>(res);
}

export async function resumeEncounter(
  encounterId: string,
  payload: HumanDecisionRequest,
): Promise<EncounterCreateResponse> {
  const res = await fetch(`${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle<EncounterCreateResponse>(res);
}

export async function listEncounters(patientId?: string): Promise<EncounterListResponse> {
  const url = patientId
    ? `${API_BASE_URL}/encounters?patient_id=${encodeURIComponent(patientId)}`
    : `${API_BASE_URL}/encounters`;
  const res = await fetch(url);
  return handle<EncounterListResponse>(res);
}

export async function getEncounter(encounterId: string): Promise<EncounterDetail> {
  const res = await fetch(`${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}`);
  return handle<EncounterDetail>(res);
}

export function streamUrl(encounterId: string): string {
  return `${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/stream`;
}

export function encounterFileUrl(encounterId: string): string {
  return `${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/file`;
}
