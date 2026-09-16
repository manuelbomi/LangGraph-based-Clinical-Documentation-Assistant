import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { encounterFileUrl, getEncounter } from "../api/client";
import { CodeSuggestionsList } from "../components/CodeSuggestionsList";
import { PatientSummaryCard } from "../components/PatientSummaryCard";
import { StructuredNoteCard } from "../components/StructuredNoteCard";

const FINAL_STATUS_LABEL: Record<string, string> = {
  added_to_record: "Added to patient record",
  corrected_and_added: "Added to patient record (corrected)",
  rejected: "Rejected",
};

/** The "example analyses" detail view: original note, final structured
 * record, accepted ICD-10 codes, final patient summary, and the trace log
 * for one encounter. Works out of the box for the seeded example
 * encounters as well as anything a user has run themselves. */
export function EncounterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["encounter", id],
    queryFn: () => getEncounter(id as string),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return <p className="text-sm text-slate-400">Loading encounter...</p>;
  }
  if (error || !data) {
    return <p className="text-sm text-rose-600">Could not load this encounter.</p>;
  }

  const acceptedEntries = Object.entries(data.accepted_codes).filter(([, code]) => code);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <Link to="/patients" className="text-xs text-brand-700 hover:underline">
          &larr; Back to patient encounter history
        </Link>
        <h2 className="mt-1 text-xl font-semibold text-slate-900">{data.original_filename}</h2>
        <p className="text-sm text-slate-500">
          Status: {data.status.replace("_", " ")}
          {data.final_status && <> &middot; {FINAL_STATUS_LABEL[data.final_status] ?? data.final_status}</>}
          {" -- "}
          <a href={encounterFileUrl(data.id)} className="text-brand-700 hover:underline" target="_blank" rel="noreferrer">
            view original note
          </a>
        </p>
      </div>

      {data.error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">{data.error}</p>}

      <StructuredNoteCard note={data.structured_note} />

      {acceptedEntries.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">Clinician-accepted ICD-10 codes</h4>
          <ul className="space-y-0.5">
            {acceptedEntries.map(([problem, code]) => (
              <li key={problem}>
                <span className="font-mono font-medium text-brand-700">{code}</span> -- {problem}
              </li>
            ))}
          </ul>
        </div>
      )}

      <CodeSuggestionsList suggestions={data.code_suggestions} />
      <PatientSummaryCard summary={data.patient_summary} />

      {data.trace.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">Trace</h4>
          <ul className="space-y-1 text-xs text-slate-500">
            {data.trace.map((event, i) => (
              <li key={i}>
                <span className="font-mono text-slate-400">{event.node}</span> -- {event.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
