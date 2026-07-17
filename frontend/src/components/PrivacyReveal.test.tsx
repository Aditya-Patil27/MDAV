import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PrivacyReveal from "./PrivacyReveal";

describe("PrivacyReveal", () => {
  it("keeps OCR collapsed and identifiers masked until two explicit actions", () => {
    const sensitive = "Aadhaar 1234 5678 9012";
    render(<PrivacyReveal text={sensitive} />);
    expect(screen.queryByText(/Aadhaar 1234/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show extracted text" }));
    expect(screen.getByText(/Aadhaar XXXX XXXX 9012/)).toBeInTheDocument();
    expect(screen.queryByText(sensitive)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reveal sensitive text" }));
    expect(screen.getByText(sensitive)).toBeInTheDocument();
    expect(screen.getByText(/authorized to view it/i)).toBeInTheDocument();
  });
});
