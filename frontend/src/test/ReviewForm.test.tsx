import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { InterruptPayload } from "../api/types";
import { ReviewForm } from "../components/ReviewForm";

const INTERRUPT: InterruptPayload = {
  original_filename: "outpatient_pharyngitis_avery_kim.txt",
  structured_note: {
    chief_complaint: "Sore throat and low-grade fever for 3 days.",
    problem_list: [{ description: "Acute pharyngitis, likely streptococcal." }],
    medications: [{ name: "Amoxicillin", dosage: "500 mg", frequency: "twice daily for 10 days", notes: "New" }],
    allergies: [],
    follow_up_instructions: ["Return if symptoms worsen."],
    referrals: [],
    vitals: {
      blood_pressure: "118/76",
      heart_rate: "88",
      temperature: "100.4 F",
      respiratory_rate: "16",
      oxygen_saturation: "98%",
      weight: "",
      height: "",
    },
  },
  code_suggestions: [
    {
      problem: "Acute pharyngitis, likely streptococcal.",
      suggestions: [
        { code: "J02.9", description: "Acute pharyngitis unspecified", score: 0.91 },
        { code: "J06.9", description: "Acute upper respiratory infection unspecified", score: 0.62 },
      ],
    },
  ],
  patient_summary: "You have strep throat and were started on an antibiotic.",
};

describe("ReviewForm", () => {
  it("pre-fills the structured note fields", () => {
    render(<ReviewForm interrupt={INTERRUPT} onDecision={vi.fn()} />);

    expect(screen.getByLabelText(/^chief complaint$/i)).toHaveValue("Sore throat and low-grade fever for 3 days.");
    expect(screen.getByLabelText(/medication 1 name/i)).toHaveValue("Amoxicillin");
    expect(screen.getByLabelText(/^patient summary$/i)).toHaveValue(
      "You have strep throat and were started on an antibiotic.",
    );
  });

  it("calls onDecision with approve, no corrected fields, and no accepted codes by default", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<ReviewForm interrupt={INTERRUPT} onDecision={onDecision} />);

    await user.click(screen.getByRole("button", { name: /^approve$/i }));

    expect(onDecision).toHaveBeenCalledWith({
      decision: "approve",
      feedback: "",
      accepted_codes: { "Acute pharyngitis, likely streptococcal.": null },
    });
  });

  it("calls onDecision with reject and the reviewer note as feedback", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<ReviewForm interrupt={INTERRUPT} onDecision={onDecision} />);

    await user.type(screen.getByLabelText(/reviewer note/i), "Not accurate, rejecting.");
    await user.click(screen.getByRole("button", { name: /^reject$/i }));

    expect(onDecision).toHaveBeenCalledWith(
      expect.objectContaining({ decision: "reject", feedback: "Not accurate, rejecting." }),
    );
  });

  it("reflects an accepted ICD-10 code in accepted_codes", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<ReviewForm interrupt={INTERRUPT} onDecision={onDecision} />);

    await user.click(screen.getByLabelText(/acute pharyngitis, likely streptococcal\. - j02\.9/i));
    await user.click(screen.getByRole("button", { name: /^approve$/i }));

    expect(onDecision).toHaveBeenCalledWith(
      expect.objectContaining({
        accepted_codes: { "Acute pharyngitis, likely streptococcal.": "J02.9" },
      }),
    );
  });

  it("sends edited fields as corrected_structured_note when Correct & Approve is clicked", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();
    render(<ReviewForm interrupt={INTERRUPT} onDecision={onDecision} />);

    const chiefComplaint = screen.getByLabelText(/^chief complaint$/i);
    await user.clear(chiefComplaint);
    await user.type(chiefComplaint, "Sore throat, fever, and ear pain for 3 days.");
    await user.click(screen.getByRole("button", { name: /correct & approve/i }));

    expect(onDecision).toHaveBeenCalledWith(
      expect.objectContaining({
        decision: "correct",
        corrected_structured_note: expect.objectContaining({
          chief_complaint: "Sore throat, fever, and ear pain for 3 days.",
        }),
        corrected_patient_summary: "You have strep throat and were started on an antibiotic.",
      }),
    );
  });

  it("renders the ICD-10 suggestions", () => {
    render(<ReviewForm interrupt={INTERRUPT} onDecision={vi.fn()} />);

    expect(screen.getAllByText(/J02\.9/).length).toBeGreaterThan(0);
  });

  it("disables the buttons while submitting", () => {
    render(<ReviewForm interrupt={INTERRUPT} onDecision={vi.fn()} submitting />);

    expect(screen.getByRole("button", { name: /^approve$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /correct & approve/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeDisabled();
  });
});
