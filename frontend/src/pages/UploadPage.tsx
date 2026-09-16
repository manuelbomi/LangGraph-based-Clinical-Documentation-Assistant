import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { listPatients, listSamples, resumeEncounter, runSampleDocument, uploadEncounter } from "../api/client";
import type { HumanDecisionRequest } from "../api/types";
import { GraphView } from "../components/GraphView";
import { NodePanel } from "../components/NodePanel";
import { ReviewForm } from "../components/ReviewForm";
import { useEncounterStream } from "../hooks/useEncounterStream";

const TERMINAL_STATUSES = new Set(["completed", "rejected", "error"]);

const FINAL_STATUS_LABEL: Record<string, string> = {
  added_to_record: "Added to patient record",
  corrected_and_added: "Added to patient record (corrected)",
  rejected: "Rejected",
};

export function UploadPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [patientId, setPatientId] = useState("");
  const [selectedSample, setSelectedSample] = useState("");
  const [encounterId, setEncounterId] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const queryClient = useQueryClient();

  const { data: patientsData } = useQuery({ queryKey: ["patients"], queryFn: listPatients });
  const { data: samplesData } = useQuery({ queryKey: ["samples"], queryFn: listSamples });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadEncounter(file, patientId),
    onSuccess: (data) => {
      setEncounterId(data.id);
      setGeneration(0);
    },
  });

  const sampleMutation = useMutation({
    mutationFn: (sampleId: string) => runSampleDocument(sampleId, patientId),
    onSuccess: (data) => {
      setEncounterId(data.id);
      setGeneration(0);
    },
  });

  const stream = useEncounterStream(encounterId, generation);

  const resumeMutation = useMutation({
    mutationFn: (payload: HumanDecisionRequest) => resumeEncounter(encounterId as string, payload),
    onSuccess: () => {
      setGeneration((g) => g + 1);
      queryClient.invalidateQueries({ queryKey: ["encounters"] });
      queryClient.invalidateQueries({ queryKey: ["patient", patientId] });
      queryClient.invalidateQueries({ queryKey: ["patients"] });
    },
  });

  const busy = uploadMutation.isPending || sampleMutation.isPending;
  const hasPatient = patientId !== "";
  const isRunActive = encounterId !== null;

  const suggestedSamples = samplesData?.samples.filter((s) => s.suggested_patient_id === patientId) ?? [];
  const otherSamples = samplesData?.samples.filter((s) => s.suggested_patient_id !== patientId) ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h2 className="mb-2 text-xl font-semibold text-slate-900">Upload &amp; process a clinical note</h2>
        <p className="mb-4 text-sm text-slate-500">
          Pick the patient this note belongs to, then either upload a file or run one of the bundled sample
          notes. The graph will extract a structured record from the note, suggest ICD-10 codes for each
          problem, draft a plain-language patient summary, then pause for your review. Nothing is added to the
          patient's record until you approve it.
        </p>

        <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Patient</span>
            <select
              value={patientId}
              onChange={(e) => {
                setPatientId(e.target.value);
                setSelectedSample("");
              }}
              aria-label="Choose a patient"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm sm:w-80"
            >
              <option value="">Choose a patient...</option>
              {patientsData?.patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} ({patient.mrn})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const file = fileInputRef.current?.files?.[0];
              if (file && hasPatient) uploadMutation.mutate(file);
            }}
            className="flex flex-col gap-3 rounded-lg border border-dashed border-slate-300 p-6"
          >
            <h3 className="text-sm font-semibold text-slate-800">Upload a note</h3>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt"
              aria-label="Choose a clinical note to upload"
              className="text-sm"
            />
            <button
              type="submit"
              disabled={busy || !hasPatient}
              className="self-start rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-50"
            >
              {uploadMutation.isPending ? "Uploading..." : "Upload & process"}
            </button>
            {!hasPatient && <p className="text-xs text-slate-400">Choose a patient first.</p>}
            {uploadMutation.isError && (
              <p className="text-sm text-rose-600">{(uploadMutation.error as Error).message}</p>
            )}
          </form>

          <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-6">
            <h3 className="text-sm font-semibold text-slate-800">Or run a bundled sample</h3>
            <p className="text-xs text-slate-500">
              Zero-setup demo notes bundled with this repo (see <code>sample-data/README.md</code>). Any sample
              can be run for any patient, but samples suggested for the selected patient are listed first.
            </p>
            <select
              value={selectedSample}
              onChange={(e) => setSelectedSample(e.target.value)}
              aria-label="Choose a sample note"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Choose a sample note...</option>
              {suggestedSamples.length > 0 && (
                <optgroup label="Suggested for this patient">
                  {suggestedSamples.map((sample) => (
                    <option key={sample.id} value={sample.id}>
                      {sample.label}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label={suggestedSamples.length > 0 ? "Other samples" : "All samples"}>
                {otherSamples.map((sample) => (
                  <option key={sample.id} value={sample.id}>
                    {sample.label}
                  </option>
                ))}
              </optgroup>
            </select>
            <button
              type="button"
              disabled={busy || !selectedSample || !hasPatient}
              onClick={() => sampleMutation.mutate(selectedSample)}
              className="self-start rounded-md bg-slate-800 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-900 disabled:opacity-50"
            >
              {sampleMutation.isPending ? "Starting..." : "Run sample note"}
            </button>
            {!hasPatient && <p className="text-xs text-slate-400">Choose a patient first.</p>}
            {sampleMutation.isError && (
              <p className="text-sm text-rose-600">{(sampleMutation.error as Error).message}</p>
            )}
          </div>
        </div>
      </div>

      {isRunActive && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-900">Live run</h3>
            <p className="text-sm text-slate-500">
              Status:{" "}
              <span className="font-medium text-slate-700">
                {stream.status === "connecting" ? "connecting..." : stream.status.replace("_", " ")}
              </span>
              {stream.finalStatus && (
                <span className="ml-2 text-slate-500">
                  &middot; {FINAL_STATUS_LABEL[stream.finalStatus] ?? stream.finalStatus}
                </span>
              )}
            </p>
          </div>

          {stream.error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">{stream.error}</p>}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <GraphView currentNode={stream.currentNode} completedNodes={stream.completedNodes} />
            <NodePanel
              structuredNote={stream.structuredNote}
              codeSuggestions={stream.codeSuggestions}
              patientSummary={stream.patientSummary}
              trace={stream.trace}
            />
          </div>

          {stream.status === "awaiting_human" && stream.interrupt && (
            <ReviewForm
              interrupt={stream.interrupt}
              submitting={resumeMutation.isPending}
              onDecision={(decision) => resumeMutation.mutate(decision)}
            />
          )}

          {TERMINAL_STATUSES.has(stream.status) && encounterId && (
            <p className="rounded-md bg-slate-100 p-3 text-sm text-slate-600">
              Done.{" "}
              <Link to={`/encounters/${encounterId}`} className="font-medium text-brand-700 hover:underline">
                View this encounter in the patient's history
              </Link>
              .
            </p>
          )}
        </div>
      )}
    </div>
  );
}
