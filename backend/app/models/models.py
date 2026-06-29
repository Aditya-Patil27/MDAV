from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    doc_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")
    verification_job = relationship("VerificationJob", back_populates="document", uselist=False)


class VerificationJob(Base):
    __tablename__ = "verification_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), unique=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    document = relationship("Document", back_populates="verification_job")
    ocr_result = relationship("OCRResult", back_populates="job", uselist=False)
    semantic_result = relationship("SemanticResult", back_populates="job", uselist=False)
    vision_result = relationship("VisionResult", back_populates="job", uselist=False)
    signature_result = relationship("SignatureResult", back_populates="job", uselist=False)
    fused_result = relationship("FusedResult", back_populates="job", uselist=False)
    audit_log = relationship("AuditLog", back_populates="job", uselist=False)


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    raw_text = Column(Text)
    extracted_fields = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("VerificationJob", back_populates="ocr_result")


class SemanticResult(Base):
    __tablename__ = "semantic_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    aadhaar_valid = Column(Boolean)
    pan_valid = Column(Boolean)
    dates_valid = Column(Boolean)
    field_presence_valid = Column(Boolean)
    consistency_score = Column(Float)
    validation_details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("VerificationJob", back_populates="semantic_result")


class VisionResult(Base):
    __tablename__ = "vision_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    tamper_probability = Column(Float)
    confidence = Column(Float)
    heatmap_path = Column(String(500))
    explanation = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("VerificationJob", back_populates="vision_result")


class SignatureResult(Base):
    __tablename__ = "signature_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    signature_detected = Column(Boolean)
    certificate_valid = Column(Boolean)
    hash_valid = Column(Boolean)
    validation_result = Column(String(50))
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("VerificationJob", back_populates="signature_result")


class FusedResult(Base):
    __tablename__ = "fused_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    visual_score = Column(Float)
    semantic_score = Column(Float)
    signature_score = Column(Float)
    layout_score = Column(Float)
    qr_score = Column(Float)
    diffusion_score = Column(Float)
    final_score = Column(Float)
    conflict = Column(Float)
    decision = Column(String(50))
    reason_summary = Column(Text)
    # Per-branch payload (score + belief masses + branch-specific details) so the
    # frontend can render every branch generically, including new ones.
    branches = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("VerificationJob", back_populates="fused_result")


class ReviewFeedback(Base):
    """Human-confirmed ground truth for a verification, used to calibrate the
    Dempster-Shafer source reliabilities. ``true_label`` is 'authentic'|'forged'."""

    __tablename__ = "review_feedback"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"), index=True)
    document_id = Column(String, ForeignKey("documents.id"))
    true_label = Column(String(20), nullable=False)
    reviewer = Column(String(255))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("verification_jobs.id"))
    document_hash = Column(String(255))
    verification_timestamp = Column(DateTime, default=datetime.utcnow)
    verification_status = Column(String(50))
    authenticity_score = Column(Float)
    previous_hash = Column(String(255))
    block_hash = Column(String(255))
    details = Column(JSON)

    job = relationship("VerificationJob", back_populates="audit_log")
