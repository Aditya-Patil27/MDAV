import type {
  AuditTrailData,
  DashboardStats,
  HistoryPage,
  VerificationResult,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // The status-based message is safe and sufficient for non-JSON failures.
    }
    throw new Error(message);
  }
  return response.json();
}

export async function uploadDocument(file: File): Promise<{ id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Upload failed");
  }
  return response.json();
}

export function getDocumentResults(id: string): Promise<VerificationResult> {
  return requestJson(`/api/documents/${encodeURIComponent(id)}`);
}

export function getDashboardStats(): Promise<DashboardStats> {
  return requestJson("/api/dashboard/stats");
}

export interface HistoryQuery {
  search?: string;
  decision?: string;
  doc_type?: string;
  date_from?: string;
  date_to?: string;
  sort?: "date_desc" | "date_asc" | "score_desc" | "score_asc";
  page?: number;
  page_size?: number;
}

export function getHistory(query: HistoryQuery = {}): Promise<HistoryPage> {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  return requestJson(`/api/dashboard/history?${params.toString()}`);
}

export function getRecentHistory() {
  return requestJson<HistoryPage["items"]>("/api/dashboard/recent");
}

export function getAuditTrail(id: string): Promise<AuditTrailData> {
  return requestJson(`/api/documents/${encodeURIComponent(id)}/audit`);
}

export type {
  AuditTrailData,
  DashboardStats,
  HistoryPage,
  VerificationResult,
} from "@/types";
