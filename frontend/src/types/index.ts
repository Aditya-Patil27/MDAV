export type Decision = "APPROVED" | "REVIEW_REQUIRED" | "FLAGGED";

export type BranchStatus =
  | "active"
  | "unavailable"
  | "not_applicable"
  | "error"
  | "inconclusive"
  | "pending"
  | "inactive"
  | "mock";

export interface BranchBelief {
  authentic: number;
  forged: number;
  uncertain: number;
  belief?: number;
  plausibility?: number;
  pignistic?: number;
  source?: string;
  details?: Record<string, unknown>;
}

export interface BranchInfo {
  branch?: string;
  display_name?: string;
  label: string;
  status: BranchStatus;
  applicable?: boolean;
  raw_probability?: number | null;
  probability_label?: string | null;
  confidence?: number | null;
  reliability?: number | null;
  raw_mass?: BranchBelief | null;
  belief?: BranchBelief | null;
  mass?: BranchBelief | null;
  score?: number | null;
  raw_score?: number | null;
  score_label?: string;
  reason?: string;
  detail: Record<string, unknown>;
}

export interface OCRResult {
  raw_text: string | null;
  extracted_fields: Record<string, unknown> | null;
  confidence: number | null;
}

export interface SemanticResult {
  aadhaar_valid: boolean | null;
  pan_valid: boolean | null;
  dates_valid: boolean | null;
  field_presence_valid: boolean | null;
  consistency_score: number | null;
  validation_details: Record<string, unknown> | null;
  status?: string | null;
}

export interface VisionResult {
  tamper_probability: number | null;
  confidence: number | null;
  heatmap_path: string | null;
  explanation: string | null;
}

export interface SignatureResult {
  signature_detected: boolean | null;
  certificate_valid: boolean | null;
  hash_valid: boolean | null;
  validation_result: string | null;
  details: Record<string, unknown> | null;
}

export interface FusedResult {
  visual_score: number | null;
  semantic_score: number | null;
  signature_score: number | null;
  layout_score?: number | null;
  qr_score?: number | null;
  diffusion_score?: number | null;
  final_score: number | null;
  decision_score?: number | null;
  score_formula?: string | null;
  authentic_mass?: number | null;
  forged_mass?: number | null;
  uncertainty_mass?: number | null;
  conflict?: number | null;
  decision: Decision;
  reason_summary: string;
  branches?: Record<string, BranchInfo> | null;
  decision_thresholds?: Record<string, number> | null;
}

export interface VerificationResult {
  document_id: string;
  filename: string;
  doc_type: string | null;
  doc_side?: string | null;
  doc_type_confidence?: number | null;
  doc_type_source?: string | null;
  possible_doc_type?: string | null;
  preview_url?: string | null;
  status: string;
  ocr: OCRResult | null;
  semantic: SemanticResult | null;
  vision: VisionResult | null;
  signature: SignatureResult | null;
  fused: FusedResult | null;
  created_at: string;
  verified_at?: string | null;
}

export interface ActivityPoint {
  date: string;
  approved: number;
  review_required: number;
  flagged: number;
}

export interface BranchAvailability {
  active: number;
  total: number;
  rate: number;
}

export interface DashboardStats {
  total_documents: number;
  total_verifications: number;
  approved_count: number;
  flagged_count: number;
  review_required_count: number;
  average_uncertainty?: number | null;
  average_conflict?: number | null;
  verifications_last_7_days?: number;
  activity?: ActivityPoint[];
  branch_availability?: Record<string, BranchAvailability>;
}

export interface HistoryItem {
  document_id: string;
  filename: string;
  doc_type: string | null;
  doc_side?: string | null;
  doc_type_confidence?: number | null;
  doc_type_source?: string | null;
  decision: Decision | null;
  final_score: number | null;
  uncertainty?: number | null;
  conflict?: number | null;
  active_branches?: number;
  total_branches?: number;
  created_at: string;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AuditTrailData {
  id: string;
  document_hash: string;
  verification_timestamp: string;
  verification_status: Decision | string;
  authenticity_score: number | null;
  previous_hash: string | null;
  block_hash: string | null;
  score_formula?: string | null;
}
