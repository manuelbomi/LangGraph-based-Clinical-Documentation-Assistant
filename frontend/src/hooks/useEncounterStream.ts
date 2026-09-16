import { useEffect, useState } from "react";

import { streamUrl } from "../api/client";
import {
  emptyStructuredNote,
  type EncounterStatus,
  type GraphNodeName,
  type InterruptPayload,
  type ProblemCodeSuggestions,
  type StructuredClinicalNote,
  type TraceEventOut,
} from "../api/types";

export interface EncounterStreamState {
  status: EncounterStatus | "connecting";
  currentNode: GraphNodeName | null;
  completedNodes: GraphNodeName[];
  structuredNote: StructuredClinicalNote;
  codeSuggestions: ProblemCodeSuggestions[];
  patientSummary: string | null;
  trace: TraceEventOut[];
  interrupt: InterruptPayload | null;
  finalStatus: string | null;
  error: string | null;
}

const INITIAL_STATE: EncounterStreamState = {
  status: "connecting",
  currentNode: null,
  completedNodes: [],
  structuredNote: emptyStructuredNote(),
  codeSuggestions: [],
  patientSummary: null,
  trace: [],
  interrupt: null,
  finalStatus: null,
  error: null,
};

const TERMINAL_STATUSES = new Set(["completed", "rejected", "error"]);

/**
 * Subscribes to `GET /encounters/{id}/stream` (Server-Sent Events) and folds
 * the incoming events into a single state object a component can render
 * directly -- driving both the live GraphView highlighting and the
 * structured-note / ICD-10-suggestion / patient-summary output panels.
 */
export function useEncounterStream(encounterId: string | null, generation = 0): EncounterStreamState {
  const [state, setState] = useState<EncounterStreamState>(INITIAL_STATE);

  useEffect(() => {
    if (!encounterId) {
      setState(INITIAL_STATE);
      return;
    }

    setState({ ...INITIAL_STATE, status: "connecting" });
    const source = new EventSource(streamUrl(encounterId));

    source.addEventListener("node", (evt) => {
      const data = JSON.parse((evt as MessageEvent).data) as {
        node: GraphNodeName;
        output: Record<string, unknown>;
        trace: TraceEventOut[];
      };
      setState((prev) => ({
        ...prev,
        status: "running",
        currentNode: data.node,
        completedNodes: prev.completedNodes.includes(data.node)
          ? prev.completedNodes
          : [...prev.completedNodes, data.node],
        structuredNote:
          (data.output.structured_note as StructuredClinicalNote | undefined) ?? prev.structuredNote,
        codeSuggestions:
          (data.output.code_suggestions as ProblemCodeSuggestions[] | undefined) ?? prev.codeSuggestions,
        patientSummary: (data.output.patient_summary as string | undefined) ?? prev.patientSummary,
        trace: [...prev.trace, ...data.trace],
      }));
    });

    source.addEventListener("interrupt", (evt) => {
      const data = JSON.parse((evt as MessageEvent).data) as InterruptPayload;
      setState((prev) => ({
        ...prev,
        status: "awaiting_human",
        currentNode: "clinician_review",
        completedNodes: prev.completedNodes.includes("clinician_review")
          ? prev.completedNodes
          : [...prev.completedNodes, "clinician_review"],
        structuredNote: data.structured_note ?? prev.structuredNote,
        codeSuggestions: data.code_suggestions ?? prev.codeSuggestions,
        patientSummary: data.patient_summary ?? prev.patientSummary,
        interrupt: data,
      }));
    });

    source.addEventListener("done", (evt) => {
      const data = JSON.parse((evt as MessageEvent).data) as {
        status: EncounterStatus;
        final_status: string | null;
      };
      setState((prev) => ({
        ...prev,
        status: data.status,
        finalStatus: data.final_status,
        currentNode: TERMINAL_STATUSES.has(data.status) ? "finalize" : prev.currentNode,
        completedNodes:
          TERMINAL_STATUSES.has(data.status) && !prev.completedNodes.includes("finalize")
            ? [...prev.completedNodes, "finalize"]
            : prev.completedNodes,
      }));
      source.close();
    });

    source.addEventListener("replay", (evt) => {
      const data = JSON.parse((evt as MessageEvent).data) as {
        status: EncounterStatus;
        trace: TraceEventOut[];
        state_snapshot: Record<string, unknown>;
        final_status: string | null;
      };
      setState((prev) => ({
        ...prev,
        status: data.status,
        trace: data.trace,
        structuredNote:
          (data.state_snapshot.structured_note as StructuredClinicalNote | undefined) ?? prev.structuredNote,
        codeSuggestions:
          (data.state_snapshot.code_suggestions as ProblemCodeSuggestions[] | undefined) ?? prev.codeSuggestions,
        patientSummary: (data.state_snapshot.patient_summary as string | undefined) ?? prev.patientSummary,
        finalStatus: data.final_status,
      }));
    });

    source.addEventListener("error", (evt) => {
      // Only MessageEvents carry a backend-emitted `error` payload; a plain
      // connection failure fires this same listener with no `.data`.
      const data = (evt as MessageEvent).data;
      if (typeof data === "string") {
        const parsed = JSON.parse(data) as { message: string };
        setState((prev) => ({ ...prev, status: "error", error: parsed.message }));
        source.close();
      }
    });

    source.onerror = () => {
      setState((prev) =>
        TERMINAL_STATUSES.has(prev.status)
          ? prev
          : { ...prev, error: prev.error ?? "Connection to the encounter stream was lost." },
      );
    };

    return () => {
      source.close();
    };
    // `generation` is bumped by callers (e.g. after POST /resume) to force
    // a fresh EventSource connection against the new background task.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encounterId, generation]);

  return state;
}
