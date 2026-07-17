from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    message: str


class VerificationStatus(BaseModel):
    job_id: str
    status: str
    message: str


class OCRResultResponse(BaseModel):
    raw_text: Optional[str]
    extracted_fields: Optional[dict]
    confidence: Optional[float]


class SemanticResultResponse(BaseModel):
    aadhaar_valid: Optional[bool]
    pan_valid: Optional[bool]
    dates_valid: Optional[bool]
    field_presence_valid: Optional[bool]
    consistency_score: Optional[float]
    validation_details: Optional[dict]
    status: Optional[str] = None


class VisionResultResponse(BaseModel):
    tamper_probability: Optional[float]
    confidence: Optional[float]
    heatmap_path: Optional[str]
    explanation: Optional[str]


class SignatureResultResponse(BaseModel):
    signature_detected: Optional[bool]
    certificate_valid: Optional[bool]
    hash_valid: Optional[bool]
    validation_result: Optional[str]
    details: Optional[dict]


class FusedResultResponse(BaseModel):
    visual_score: Optional[float]
    semantic_score: Optional[float]
    signature_score: Optional[float]
    layout_score: Optional[float] = None
    qr_score: Optional[float] = None
    diffusion_score: Optional[float] = None
    final_score: Optional[float]
    decision_score: Optional[float] = None
    score_formula: Optional[str] = None
    authentic_mass: Optional[float] = None
    forged_mass: Optional[float] = None
    uncertainty_mass: Optional[float] = None
    conflict: Optional[float] = None
    decision: Optional[str]
    reason_summary: Optional[str]
    # Per-branch payload (score + belief + detail) for generic UI rendering.
    branches: Optional[dict] = None
    decision_thresholds: Optional[dict] = None


class VerificationResultResponse(BaseModel):
    document_id: str
    filename: str
    doc_type: Optional[str]
    doc_side: Optional[str] = None
    doc_type_confidence: Optional[float] = None
    doc_type_source: Optional[str] = None
    possible_doc_type: Optional[str] = None
    preview_url: Optional[str] = None
    status: str
    ocr: Optional[OCRResultResponse]
    semantic: Optional[SemanticResultResponse]
    vision: Optional[VisionResultResponse]
    signature: Optional[SignatureResultResponse]
    fused: Optional[FusedResultResponse]
    created_at: datetime
    verified_at: Optional[datetime] = None


class AuditLogResponse(BaseModel):
    id: str
    document_hash: str
    verification_timestamp: datetime
    verification_status: str
    authenticity_score: Optional[float]
    previous_hash: Optional[str] = None
    block_hash: Optional[str]
    score_formula: Optional[str] = None


class FeedbackRequest(BaseModel):
    true_label: str  # "authentic" | "forged"
    reviewer: Optional[str] = None
    notes: Optional[str] = None


class DashboardStats(BaseModel):
    total_documents: int
    total_verifications: int
    approved_count: int
    flagged_count: int
    review_required_count: int
    average_uncertainty: Optional[float] = None
    average_conflict: Optional[float] = None
    verifications_last_7_days: int = 0
    activity: List[dict] = Field(default_factory=list)
    branch_availability: dict = Field(default_factory=dict)


class HistoryItem(BaseModel):
    document_id: str
    filename: str
    doc_type: Optional[str]
    doc_side: Optional[str] = None
    doc_type_confidence: Optional[float] = None
    doc_type_source: Optional[str] = None
    decision: Optional[str]
    final_score: Optional[float]
    uncertainty: Optional[float] = None
    conflict: Optional[float] = None
    active_branches: int = 0
    total_branches: int = 0
    created_at: datetime


class HistoryPage(BaseModel):
    items: List[HistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int
