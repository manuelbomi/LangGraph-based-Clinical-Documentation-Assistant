import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getPatient, listPatients } from "../api/client";
import type { EncounterStatus } from "../api/types";

const STATUS_BADGE: Record<EncounterStatus, string> = {
  pending: "bg-slate-100 text-slate-600",
  running: "bg-sky-100 text-sky-700",
  awaiting_human: "bg-amber-100 text-amber-700",
  completed: "bg-emerald-100 text-emerald-700",
  rejected: "bg-rose-100 text-rose-700",
  error: "bg-rose-100 text-rose-700",
};

function PatientEncounters({ patientId }: { patientId: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["patient", patientId], queryFn: () => getPatient(patientId) });

  if (isLoading || !data) {
    return <p className="text-sm text-slate-400">Loading encounters...</p>;
  }

  if (data.encounters.length === 0) {
    return <p className="text-sm text-slate-400">No encounters processed for this patient yet.</p>;
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="text-xs text-slate-400">
          <th className="pb-1 pr-2">Note</th>
          <th className="pb-1 pr-2">Status</th>
          <th className="pb-1 pr-2">Outcome</th>
          <th className="pb-1">Processed</th>
        </tr>
      </thead>
      <tbody>
        {data.encounters.map((encounter) => (
          <tr key={encounter.id} className="border-t border-slate-100">
            <td className="py-1.5 pr-2">
              <Link to={`/encounters/${encounter.id}`} className="font-medium text-brand-700 hover:underline">
                {encounter.original_filename}
              </Link>
            </td>
            <td className="py-1.5 pr-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[encounter.status]}`}>
                {encounter.status.replace("_", " ")}
              </span>
            </td>
            <td className="py-1.5 pr-2 text-slate-500">{encounter.final_status ?? "--"}</td>
            <td className="py-1.5 text-slate-400">{new Date(encounter.created_at).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Per-patient encounter history / "example analyses" list -- works out of
 * the box against the seeded example encounters (see
 * backend/scripts/seed_examples.py) once the backend is running. */
export function PatientHistoryPage() {
  const { data, isLoading } = useQuery({ queryKey: ["patients"], queryFn: listPatients });
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h2 className="text-xl font-semibold text-slate-900">Patient encounter history</h2>
      <p className="text-sm text-slate-500">
        Every note ever processed for a patient, with its review outcome. Click a patient to see their
        encounters.
      </p>

      {isLoading && <p className="text-sm text-slate-400">Loading patients...</p>}

      <div className="space-y-3">
        {data?.patients.map((patient) => (
          <div key={patient.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <button
              type="button"
              onClick={() => setExpanded((prev) => (prev === patient.id ? null : patient.id))}
              className="flex w-full items-center justify-between text-left"
            >
              <div>
                <div className="font-medium text-slate-900">{patient.name}</div>
                <div className="text-xs text-slate-400">
                  {patient.mrn} &middot; DOB {patient.date_of_birth}
                </div>
              </div>
              <span className="text-xs text-brand-700">{expanded === patient.id ? "Hide" : "View encounters"}</span>
            </button>
            {expanded === patient.id && (
              <div className="mt-3 border-t border-slate-100 pt-3">
                <PatientEncounters patientId={patient.id} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
