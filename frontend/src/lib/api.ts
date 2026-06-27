const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface VerificationResult {
  document_id: string;
  filename: string;
  doc_type: string;
  status: string;
  ocr: {
    raw_text: string;
    extracted_fields: Record<string, unknown>;
    confidence: number;
  } | null;
  semantic: {
    aadhaar_valid: boolean | null;
    pan_valid: boolean | null;
    dates_valid: boolean | null;
    field_presence_valid: boolean | null;
    consistency_score: number;
    validation_details: Record<string, unknown>;
  } | null;
  vision: {
    tamper_probability: number;
    confidence: number;
    heatmap_path: string | null;
    explanation: string;
  } | null;
  signature: {
    signature_detected: boolean;
    certificate_valid: boolean | null;
    hash_valid: boolean | null;
    validation_result: string;
    details: Record<string, unknown>;
  } | null;
  fused: {
    visual_score: number;
    semantic_score: number;
    signature_score: number;
    final_score: number;
    decision: string;
    reason_summary: string;
  } | null;
  created_at: string;
}

export interface DashboardStats {
  total_documents: number;
  total_verifications: number;
  approved_count: number;
  flagged_count: number;
  review_required_count: number;
}

export interface HistoryItem {
  document_id: string;
  filename: string;
  doc_type: string;
  decision: string;
  final_score: number;
  created_at: string;
}

export async function uploadDocument(file: File): Promise<{ id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function getDocumentResults(id: string): Promise<VerificationResult> {
  const response = await fetch(`${API_BASE}/api/documents/${id}`);
  if (!response.ok) throw new Error("Failed to fetch results");
  return response.json();
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await fetch(`${API_BASE}/api/dashboard/stats`);
  if (!response.ok) throw new Error("Failed to fetch stats");
  return response.json();
}

export async function getRecentHistory(): Promise<HistoryItem[]> {
  const response = await fetch(`${API_BASE}/api/dashboard/recent`);
  if (!response.ok) throw new Error("Failed to fetch history");
  return response.json();
}

export interface AuditTrail {
  id: string;
  document_hash: string;
  verification_timestamp: string;
  verification_status: string;
  authenticity_score: number;
  previous_hash: string | null;
  block_hash: string;
}

export async function getAuditTrail(id: string): Promise<AuditTrail> {
  const response = await fetch(`${API_BASE}/api/documents/${id}/audit`);
  if (!response.ok) throw new Error("Failed to fetch audit trail");
  return response.json();
}
