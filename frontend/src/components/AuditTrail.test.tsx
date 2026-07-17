import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAuditTrail } from "@/lib/api";
import AuditTrail from "./AuditTrail";

vi.mock("@/lib/api", () => ({ getAuditTrail: vi.fn() }));

describe("AuditTrail", () => {
  beforeEach(() => {
    vi.mocked(getAuditTrail).mockResolvedValue({
      id: "audit-synthetic",
      document_hash: "a".repeat(64),
      verification_timestamp: "2026-07-16T10:00:00Z",
      verification_status: "REVIEW_REQUIRED",
      authenticity_score: 0.735,
      previous_hash: "b".repeat(64),
      block_hash: "c".repeat(64),
      score_formula: "pignistic_authenticity_v1",
    });
  });

  it("describes a SHA-256 hash chain without claiming a blockchain", async () => {
    render(<AuditTrail documentId="synthetic-document" />);
    await waitFor(() => expect(screen.getByText("73.5 / 100")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Hash-chained audit record" })).toBeInTheDocument();
    expect(screen.getByText(/not a decentralized blockchain/i)).toBeInTheDocument();
    expect(screen.getByText("Review required")).toBeInTheDocument();
    expect(screen.getByText(/BetP\(A\)/)).toBeInTheDocument();
  });
});
