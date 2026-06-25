export interface VerificationResult {
  document_id: string;
  filename: string;
  doc_type: string;
  status: string;
  ocr: OCRResult | null;
  semantic: SemanticResult | null;
  vision: VisionResult | null;
  signature: SignatureResult | null;
  fused: FusedResult | null;
  created_at: string;
}

export interface OCRResult {
  raw_text: string;
  extracted_fields: Record<string, unknown>;
  confidence: number;
}

export interface SemanticResult {
  aadhaar_valid: boolean | null;
  pan_valid: boolean | null;
  dates_valid: boolean | null;
  field_presence_valid: boolean | null;
  consistency_score: number;
  validation_details: Record<string, unknown>;
}

export interface VisionResult {
  tamper_probability: number;
  confidence: number;
  heatmap_path: string | null;
  explanation: string;
}

export interface SignatureResult {
  signature_detected: boolean;
  certificate_valid: boolean | null;
  hash_valid: boolean | null;
  validation_result: string;
  details: Record<string, unknown>;
}

export interface FusedResult {
  visual_score: number;
  semantic_score: number;
  signature_score: number;
  final_score: number;
  decision: "APPROVED" | "FLAGGED" | "REVIEW_REQUIRED";
  reason_summary: string;
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

export interface AuditLog {
  id: string;
  document_hash: string;
  verification_timestamp: string;
  verification_status: string;
  authenticity_score: number;
  previous_hash: string;
  block_hash: string;
}
