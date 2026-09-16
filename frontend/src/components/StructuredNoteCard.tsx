import type { StructuredClinicalNote } from "../api/types";

interface StructuredNoteCardProps {
  note: StructuredClinicalNote;
}

const VITAL_LABELS: Record<keyof StructuredClinicalNote["vitals"], string> = {
  blood_pressure: "Blood pressure",
  heart_rate: "Heart rate",
  temperature: "Temperature",
  respiratory_rate: "Respiratory rate",
  oxygen_saturation: "Oxygen saturation",
  weight: "Weight",
  height: "Height",
};

/** Renders the structured note extracted from a clinician's free-text note.
 * Every field here is meant to reflect only what the clinician actually
 * wrote -- see the root README's Scope & Safety section and the
 * `extract_structured_note` prompt, which is constrained to never invent or
 * infer new clinical content. */
export function StructuredNoteCard({ note }: StructuredNoteCardProps) {
  const vitalEntries = (Object.keys(VITAL_LABELS) as (keyof StructuredClinicalNote["vitals"])[]).filter(
    (key) => note.vitals[key],
  );

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <h4 className="text-xs font-semibold uppercase text-slate-500">Structured note</h4>

      {note.chief_complaint && (
        <div>
          <div className="text-xs font-medium text-slate-500">Chief complaint</div>
          <div>{note.chief_complaint}</div>
        </div>
      )}

      {note.problem_list.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500">Problem list</div>
          <ul className="list-inside list-disc space-y-0.5">
            {note.problem_list.map((problem, i) => (
              <li key={i}>{problem.description}</li>
            ))}
          </ul>
        </div>
      )}

      {note.medications.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Medications</div>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-slate-400">
                <th className="pb-1 pr-2">Name</th>
                <th className="pb-1 pr-2">Dosage</th>
                <th className="pb-1 pr-2">Frequency</th>
                <th className="pb-1">Notes</th>
              </tr>
            </thead>
            <tbody>
              {note.medications.map((med, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-1 pr-2 font-medium">{med.name}</td>
                  <td className="py-1 pr-2">{med.dosage}</td>
                  <td className="py-1 pr-2">{med.frequency}</td>
                  <td className="py-1 text-slate-500">{med.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {note.allergies.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500">Allergies</div>
          <ul className="list-inside list-disc space-y-0.5">
            {note.allergies.map((allergy, i) => (
              <li key={i}>{allergy}</li>
            ))}
          </ul>
        </div>
      )}

      {note.follow_up_instructions.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500">Follow-up instructions</div>
          <ul className="list-inside list-disc space-y-0.5">
            {note.follow_up_instructions.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {note.referrals.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500">Referrals</div>
          <ul className="list-inside list-disc space-y-0.5">
            {note.referrals.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {vitalEntries.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500">Vitals</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-3">
            {vitalEntries.map((key) => (
              <div key={key}>
                <span className="text-slate-400">{VITAL_LABELS[key]}: </span>
                {note.vitals[key]}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
