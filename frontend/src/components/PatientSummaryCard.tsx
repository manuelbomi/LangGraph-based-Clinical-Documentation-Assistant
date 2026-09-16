interface PatientSummaryCardProps {
  summary: string | null;
}

/** Renders the plain-language after-visit summary generated for the
 * patient. This is a rephrasing/simplification of the structured note
 * only -- it must never introduce new clinical content, and (like every
 * other output in this app) is not final until a clinician approves it. */
export function PatientSummaryCard({ summary }: PatientSummaryCardProps) {
  if (!summary) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">Patient-facing summary (draft)</h4>
      <p className="whitespace-pre-wrap text-slate-700">{summary}</p>
    </div>
  );
}
