import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["APPROVED", "Approved", "text-green-800"],
    ["REVIEW_REQUIRED", "Review required", "text-amber-800"],
    ["FLAGGED", "Flagged", "text-red-800"],
  ])("renders %s with accessible wording and the intended tone", (decision, label, colorClass) => {
    render(<StatusBadge decision={decision} />);
    expect(screen.getByText(label)).toHaveClass(colorClass);
  });

  it("normalizes a pending branch to unavailable", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("renders not-applicable evidence neutrally", () => {
    render(<StatusBadge status="not_applicable" />);
    expect(screen.getByText("Not applicable")).toHaveClass("text-gray-700");
  });
});
