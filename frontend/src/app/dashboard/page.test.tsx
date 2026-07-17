import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getDashboardStats, getHistory } from "@/lib/api";
import DashboardPage from "./page";

vi.mock("@/lib/api", () => ({ getDashboardStats: vi.fn(), getHistory: vi.fn() }));
vi.mock("recharts", () => {
  const Container = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  const Mark = () => <span />;
  return { ResponsiveContainer: Container, BarChart: Container, PieChart: Container, Pie: Container, Bar: Mark, Cell: Mark, CartesianGrid: Mark, Tooltip: Mark, XAxis: Mark, YAxis: Mark };
});

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(getDashboardStats).mockResolvedValue({ total_documents: 3, total_verifications: 3, approved_count: 0, review_required_count: 3, flagged_count: 0, activity: [], branch_availability: {} });
    vi.mocked(getHistory).mockResolvedValue({ items: [], total: 3, page: 1, page_size: 5, total_pages: 1 });
  });

  it("shows review-required outcomes and an external decision legend", async () => {
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument());
    const reviewCardLabel = screen.getAllByText("Review required")[0];
    expect(reviewCardLabel.parentElement).toHaveTextContent("3");
    const legend = screen.getByRole("list", { name: "Decision counts" });
    expect(within(legend).getByText("Approved")).toBeInTheDocument();
    expect(within(legend).getByText("Review required")).toBeInTheDocument();
    expect(within(legend).getByText("Flagged")).toBeInTheDocument();
  });
});
