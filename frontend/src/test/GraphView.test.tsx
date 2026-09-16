import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GraphView } from "../components/GraphView";

describe("GraphView", () => {
  it("renders all six graph node labels", () => {
    render(<GraphView currentNode="code_lookup" completedNodes={["ingest", "extract_structured"]} />);

    expect(screen.getByText(/1\. Ingest/)).toBeInTheDocument();
    expect(screen.getByText(/2\. Extract Structured Note/)).toBeInTheDocument();
    expect(screen.getByText(/3\. ICD-10 Code Lookup/)).toBeInTheDocument();
    expect(screen.getByText(/6\. Finalize/)).toBeInTheDocument();
  });
});
