import type { ProblemCodeSuggestions, StructuredClinicalNote, TraceEventOut } from "../api/types";
import { CodeSuggestionsList } from "./CodeSuggestionsList";
import { PatientSummaryCard } from "./PatientSummaryCard";
import { StructuredNoteCard } from "./StructuredNoteCard";

interface NodePanelProps {
  structuredNote: StructuredClinicalNote;
  codeSuggestions: ProblemCodeSuggestions[];
  patientSummary: string | null;
  trace: TraceEventOut[];
}

const hasStructuredNoteContent = (note: StructuredClinicalNote): boolean =>
  Boolean(
    note.chief_complaint ||
      note.problem_list.length ||
      note.medications.length ||
      note.allergies.length ||
      note.follow_up_instructions.length ||
      note.referrals.length,
  );

/** Live output panel for the Upload & Process page: shows the structured
 * note, suggested ICD-10 codes, and generated patient summary as they
 * arrive over the SSE stream, plus the raw node trace log. */
export function NodePanel({ structuredNote, codeSuggestions, patientSummary, trace }: NodePanelProps) {
  return (
    <div className="space-y-4">
      {hasStructuredNoteContent(structuredNote) && <StructuredNoteCard note={structuredNote} />}
      <CodeSuggestionsList suggestions={codeSuggestions} />
      <PatientSummaryCard summary={patientSummary} />

      {trace.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">Trace</h4>
          <ul className="space-y-1 text-xs text-slate-500">
            {trace.map((event, i) => (
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
