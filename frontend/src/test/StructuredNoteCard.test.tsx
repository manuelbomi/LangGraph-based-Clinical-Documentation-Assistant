import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StructuredClinicalNote } from "../api/types";
import { StructuredNoteCard } from "../components/StructuredNoteCard";

const NOTE: StructuredClinicalNote = {
  chief_complaint: "Follow-up for hypertension.",
  problem_list: [{ description: "Essential hypertension, well controlled." }],
  medications: [{ name: "Losartan", dosage: "50 mg", frequency: "once daily", notes: "New" }],
  allergies: ["No known drug allergies"],
  follow_up_instructions: ["Recheck blood pressure in 4 weeks."],
  referrals: [],
  vitals: {
    blood_pressure: "126/80",
    heart_rate: "74",
    temperature: "",
    respiratory_rate: "",
    oxygen_saturation: "",
    weight: "168 lb",
    height: "",
  },
};

describe("StructuredNoteCard", () => {
  it("renders the chief complaint, problem list, and medications", () => {
    render(<StructuredNoteCard note={NOTE} />);

    expect(screen.getByText("Follow-up for hypertension.")).toBeInTheDocument();
    expect(screen.getByText("Essential hypertension, well controlled.")).toBeInTheDocument();
    expect(screen.getByText("Losartan")).toBeInTheDocument();
  });

  it("only renders vitals that have a value", () => {
    render(<StructuredNoteCard note={NOTE} />);

    expect(screen.getByText("Blood pressure:", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("Temperature:", { exact: false })).not.toBeInTheDocument();
  });
});
