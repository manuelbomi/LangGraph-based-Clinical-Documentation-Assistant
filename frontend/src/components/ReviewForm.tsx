import { useState } from "react";

import type { HumanDecisionRequest, InterruptPayload, MedicationItem, StructuredClinicalNote } from "../api/types";
import { linesToList, listToLines } from "../lib/fields";
import { CodeSuggestionsList } from "./CodeSuggestionsList";

interface ReviewFormProps {
  interrupt: InterruptPayload;
  onDecision: (decision: HumanDecisionRequest) => void;
  submitting?: boolean;
}

function initialAcceptedCodes(interrupt: InterruptPayload): Record<string, string | null> {
  return Object.fromEntries(interrupt.code_suggestions.map((entry) => [entry.problem, null]));
}

/** The human-in-the-loop clinician review panel -- the safety gate this
 * whole app is built around. Nothing extracted or generated here is added
 * to a patient's record until a clinician explicitly approves, corrects, or
 * rejects it: see the root README's "Scope & Safety" section. Suggested
 * ICD-10 codes are opt-in per problem (nothing is pre-selected) and are
 * never applied automatically. */
export function ReviewForm({ interrupt, onDecision, submitting }: ReviewFormProps) {
  const note = interrupt.structured_note;
  const [chiefComplaint, setChiefComplaint] = useState(note.chief_complaint);
  const [problemLines, setProblemLines] = useState(listToLines(note.problem_list.map((p) => p.description)));
  const [medications, setMedications] = useState<MedicationItem[]>(note.medications);
  const [allergiesLines, setAllergiesLines] = useState(listToLines(note.allergies));
  const [followUpLines, setFollowUpLines] = useState(listToLines(note.follow_up_instructions));
  const [referralsLines, setReferralsLines] = useState(listToLines(note.referrals));
  const [patientSummary, setPatientSummary] = useState(interrupt.patient_summary);
  const [acceptedCodes, setAcceptedCodes] = useState<Record<string, string | null>>(() =>
    initialAcceptedCodes(interrupt),
  );
  const [feedback, setFeedback] = useState("");

  const updateMedication = (index: number, field: keyof MedicationItem, value: string) => {
    setMedications((prev) => prev.map((med, i) => (i === index ? { ...med, [field]: value } : med)));
  };

  const setAcceptedCodeForProblem = (problem: string, code: string | null) => {
    setAcceptedCodes((prev) => ({ ...prev, [problem]: code }));
  };

  const buildCorrectedNote = (): StructuredClinicalNote => ({
    chief_complaint: chiefComplaint,
    problem_list: linesToList(problemLines).map((description) => ({ description })),
    medications,
    allergies: linesToList(allergiesLines),
    follow_up_instructions: linesToList(followUpLines),
    referrals: linesToList(referralsLines),
    vitals: note.vitals,
  });

  const submit = (decision: HumanDecisionRequest["decision"]) => {
    const payload: HumanDecisionRequest = { decision, feedback, accepted_codes: acceptedCodes };
    if (decision === "correct") {
      payload.corrected_structured_note = buildCorrectedNote();
      payload.corrected_patient_summary = patientSummary;
    }
    onDecision(payload);
  };

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-amber-700">
        Clinician review required
      </h3>
      <p className="mb-4 text-sm text-amber-900">
        <strong>Not medical advice.</strong> This is an administrative documentation aid -- it summarizes and
        structures the note above, it does not diagnose or recommend treatment. Review and correct the fields
        below as needed, then Approve, Correct &amp; Approve, or Reject. Nothing is added to this patient's
        record until you decide.
      </p>

      <div className="mb-4 grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-lg border border-amber-200 bg-white p-4">
          <h4 className="text-xs font-semibold uppercase text-slate-500">Structured note (editable)</h4>

          <label className="block text-sm">
            <span className="text-xs text-slate-500">Chief complaint</span>
            <input
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              aria-label="Chief complaint"
            />
          </label>

          <label className="block text-sm">
            <span className="text-xs text-slate-500">Problem list (one per line)</span>
            <textarea
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
              rows={3}
              value={problemLines}
              onChange={(e) => setProblemLines(e.target.value)}
              aria-label="Problem list (one per line)"
            />
          </label>

          {medications.length > 0 && (
            <div className="text-sm">
              <span className="mb-1 block text-xs text-slate-500">Medications</span>
              <div className="space-y-2">
                {medications.map((med, i) => (
                  <div key={i} className="grid grid-cols-2 gap-1 rounded border border-slate-200 p-2 sm:grid-cols-4">
                    <input
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                      value={med.name}
                      onChange={(e) => updateMedication(i, "name", e.target.value)}
                      aria-label={`Medication ${i + 1} name`}
                      placeholder="Name"
                    />
                    <input
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                      value={med.dosage}
                      onChange={(e) => updateMedication(i, "dosage", e.target.value)}
                      aria-label={`Medication ${i + 1} dosage`}
                      placeholder="Dosage"
                    />
                    <input
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                      value={med.frequency}
                      onChange={(e) => updateMedication(i, "frequency", e.target.value)}
                      aria-label={`Medication ${i + 1} frequency`}
                      placeholder="Frequency"
                    />
                    <input
                      className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                      value={med.notes}
                      onChange={(e) => updateMedication(i, "notes", e.target.value)}
                      aria-label={`Medication ${i + 1} notes`}
                      placeholder="Notes"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <label className="block text-sm">
            <span className="text-xs text-slate-500">Allergies (one per line)</span>
            <textarea
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
              rows={2}
              value={allergiesLines}
              onChange={(e) => setAllergiesLines(e.target.value)}
              aria-label="Allergies (one per line)"
            />
          </label>

          <label className="block text-sm">
            <span className="text-xs text-slate-500">Follow-up instructions (one per line)</span>
            <textarea
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
              rows={3}
              value={followUpLines}
              onChange={(e) => setFollowUpLines(e.target.value)}
              aria-label="Follow-up instructions (one per line)"
            />
          </label>

          <label className="block text-sm">
            <span className="text-xs text-slate-500">Referrals (one per line)</span>
            <textarea
              className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
              rows={2}
              value={referralsLines}
              onChange={(e) => setReferralsLines(e.target.value)}
              aria-label="Referrals (one per line)"
            />
          </label>
        </div>

        <div className="space-y-3">
          <CodeSuggestionsList suggestions={interrupt.code_suggestions} />

          {interrupt.code_suggestions.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-white p-4 text-sm">
              <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                Accept a suggested code per problem
              </h4>
              <div className="space-y-3">
                {interrupt.code_suggestions.map((entry) => (
                  <fieldset key={entry.problem}>
                    <legend className="mb-1 text-xs font-medium text-slate-600">{entry.problem}</legend>
                    <div className="space-y-1">
                      <label className="flex items-center gap-2 text-xs text-slate-500">
                        <input
                          type="radio"
                          name={`codes-${entry.problem}`}
                          checked={acceptedCodes[entry.problem] == null}
                          onChange={() => setAcceptedCodeForProblem(entry.problem, null)}
                          aria-label={`${entry.problem} - none`}
                        />
                        None / reject all suggestions
                      </label>
                      {entry.suggestions.map((code) => (
                        <label key={code.code} className="flex items-center gap-2 text-xs text-slate-700">
                          <input
                            type="radio"
                            name={`codes-${entry.problem}`}
                            checked={acceptedCodes[entry.problem] === code.code}
                            onChange={() => setAcceptedCodeForProblem(entry.problem, code.code)}
                            aria-label={`${entry.problem} - ${code.code}`}
                          />
                          <span className="font-mono font-medium text-brand-700">{code.code}</span>
                          {code.description}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>
            </div>
          )}

          <label className="block rounded-lg border border-amber-200 bg-white p-4 text-sm">
            <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Patient-facing summary (editable)
            </span>
            <textarea
              className="w-full rounded border border-slate-300 p-2 text-sm"
              rows={6}
              value={patientSummary}
              onChange={(e) => setPatientSummary(e.target.value)}
              aria-label="Patient summary"
            />
          </label>
        </div>
      </div>

      <textarea
        className="mb-3 w-full rounded-md border border-slate-300 p-2 text-sm"
        rows={2}
        placeholder="Reviewer note (optional) -- why you approved, corrected, or rejected this"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        aria-label="Reviewer note"
      />

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => submit("approve")}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => submit("correct")}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Correct &amp; Approve
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => submit("reject")}
          className="rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
