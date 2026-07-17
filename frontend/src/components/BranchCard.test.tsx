import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BranchInfo } from "@/types";
import BranchCard from "./BranchCard";

const unavailable: BranchInfo = {
  label: "Conventional visual forensics",
  status: "unavailable",
  raw_probability: null,
  confidence: 0,
  reliability: 0.8,
  mass: { authentic: 0, forged: 0, uncertain: 1 },
  reason: "Model weights are unavailable.",
  detail: {},
};

describe("BranchCard", () => {
  it("renders unavailable evidence as N/A with vacuous belief, never as 50 percent", () => {
    render(<BranchCard source="visual" branch={unavailable} />);
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
    expect(screen.getByText("None")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
    expect(screen.queryByText("50.0%")).not.toBeInTheDocument();
  });

  it("keeps raw output separate from discounted evidence", () => {
    render(
      <BranchCard
        source="visual"
        branch={{ ...unavailable, status: "active", raw_probability: 0.91, confidence: 0.87, reliability: 0.8, mass: { authentic: 0.08, forged: 0.72, uncertain: 0.2 }, reason: "Localized evidence detected." }}
      />,
    );
    expect(screen.getByText("91.00%")).toBeInTheDocument();
    expect(screen.getByText("87.0%")).toBeInTheDocument();
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByText("72.0%")).toBeInTheDocument();
  });
});
