from pydantic import BaseModel, EmailStr
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
    conflict: Optional[float] = None
    decision: Optional[str]
    reason_summary: Optional[str]
    # Per-branch payload (score + belief + detail) for generic UI rendering.
    branches: Optional[dict] = None


class VerificationResultResponse(BaseModel):
    document_id: str
    filename: str
    doc_type: Optional[str]
    status: str
    ocr: Optional[OCRResultResponse]
    semantic: Optional[SemanticResultResponse]
    vision: Optional[VisionResultResponse]
    signature: Optional[SignatureResultResponse]
    fused: Optional[FusedResultResponse]
    created_at: datetime


class AuditLogResponse(BaseModel):
    id: str
    document_hash: str
    verification_timestamp: datetime
    verification_status: str
    authenticity_score: Optional[float]
    block_hash: Optional[str]


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


class HistoryItem(BaseModel):
    document_id: str
    filename: str
    doc_type: Optional[str]
    decision: Optional[str]
    final_score: Optional[float]
    created_at: datetime
