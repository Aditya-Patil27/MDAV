import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getHistory } from "@/lib/api";
import HistoryPage from "./page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({ getHistory: vi.fn() }));

describe("HistoryPage", () => {
  const filename = "an_extremely_long_synthetic_document_filename_used_only_for_layout_testing.png";

  beforeEach(() => {
    push.mockReset();
    vi.mocked(getHistory).mockResolvedValue({ items: [{ document_id: "synthetic-1", filename, doc_type: "aadhaar", doc_side: "front", decision: "REVIEW_REQUIRED", final_score: 0.445, uncertainty: 0.41, conflict: 0.12, active_branches: 3, total_branches: 6, created_at: "2026-07-16T10:00:00Z" }], total: 1, page: 1, page_size: 15, total_pages: 1 });
  });

  it("truncates long filenames accessibly and opens the result from a keyboard-capable row", async () => {
    render(<HistoryPage />);
    await waitFor(() => expect(screen.getAllByTitle(filename).length).toBeGreaterThan(0));
    screen.getAllByTitle(filename).forEach((element) => expect(element).toHaveClass("truncate"));
    fireEvent.click(screen.getByRole("link", { name: `Open results for ${filename}` }));
    expect(push).toHaveBeenCalledWith("/results?id=synthetic-1");
  });
});
