from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import os
import uuid

from app.database import get_db
from app.models.models import Document, VerificationJob, OCRResult, SemanticResult, VisionResult, SignatureResult, FusedResult, ReviewFeedback
from app.models.schemas import (
    DocumentUploadResponse,
    VerificationStatus,
    VerificationResultResponse,
    OCRResultResponse,
    SemanticResultResponse,
    VisionResultResponse,
    SignatureResultResponse,
    FusedResultResponse,
    FeedbackRequest,
)
from app.services.preprocessing import preprocess_document
from app.services.ocr_service import ocr_service
from app.services.semantic_service import semantic_validator
from app.services.vision_service import vision_service
from app.services.layout_service import layout_service
from app.services.aadhaar_qr import aadhaar_qr_service
from app.services.diffusion_service import diffusion_service
from app.services.signature_service import signature_service
from app.services.fusion_service import fusion_service
from app.services.audit_service import audit_service
from app.services.belief import from_check, vacuous

router = APIRouter()

STORAGE_PATH = os.getenv("STORAGE_PATH", "./storage")
ALLOWED_TYPES = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_SIZE = 20 * 1024 * 1024


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}",
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit",
        )

    os.makedirs(STORAGE_PATH, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(STORAGE_PATH, f"{file_id}{file_ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    doc_type = _detect_doc_type(file.filename)

    document = Document(
        id=file_id,
        filename=file.filename,
        file_type=file_ext,
        file_size=len(content),
        storage_path=file_path,
        doc_type=doc_type,
    )
    db.add(document)
    db.commit()

    job = VerificationJob(
        document_id=file_id,
        status="processing",
    )
    db.add(job)
    db.commit()

    try:
        _run_verification_pipeline(file_path, job.id, db)
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        job.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )

    return DocumentUploadResponse(
        id=file_id,
        filename=file.filename,
        file_type=file_ext,
        status="completed",
        message="Document uploaded and verified successfully",
    )


@router.get("/{doc_id}", response_model=VerificationResultResponse)
async def get_document_results(doc_id: str, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    job = db.query(VerificationJob).filter(VerificationJob.document_id == doc_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")

    ocr = db.query(OCRResult).filter(OCRResult.job_id == job.id).first()
    semantic = db.query(SemanticResult).filter(SemanticResult.job_id == job.id).first()
    vision = db.query(VisionResult).filter(VisionResult.job_id == job.id).first()
    signature = db.query(SignatureResult).filter(SignatureResult.job_id == job.id).first()
    fused = db.query(FusedResult).filter(FusedResult.job_id == job.id).first()

    return VerificationResultResponse(
        document_id=doc_id,
        filename=document.filename,
        doc_type=document.doc_type,
        status=job.status,
        ocr=OCRResultResponse(
            raw_text=ocr.raw_text if ocr else None,
            extracted_fields=ocr.extracted_fields if ocr else None,
            confidence=ocr.confidence if ocr else None,
        ) if ocr else None,
        semantic=SemanticResultResponse(
            aadhaar_valid=semantic.aadhaar_valid if semantic else None,
            pan_valid=semantic.pan_valid if semantic else None,
            dates_valid=semantic.dates_valid if semantic else None,
            field_presence_valid=semantic.field_presence_valid if semantic else None,
            consistency_score=semantic.consistency_score if semantic else None,
            validation_details=semantic.validation_details if semantic else None,
        ) if semantic else None,
        vision=VisionResultResponse(
            tamper_probability=vision.tamper_probability if vision else None,
            confidence=vision.confidence if vision else None,
            heatmap_path=vision.heatmap_path if vision else None,
            explanation=vision.explanation if vision else None,
        ) if vision else None,
        signature=SignatureResultResponse(
            signature_detected=signature.signature_detected if signature else None,
            certificate_valid=signature.certificate_valid if signature else None,
            hash_valid=signature.hash_valid if signature else None,
            validation_result=signature.validation_result if signature else None,
            details=signature.details if signature else None,
        ) if signature else None,
        fused=FusedResultResponse(
            visual_score=fused.visual_score if fused else None,
            semantic_score=fused.semantic_score if fused else None,
            signature_score=fused.signature_score if fused else None,
            layout_score=fused.layout_score if fused else None,
            qr_score=fused.qr_score if fused else None,
            diffusion_score=fused.diffusion_score if fused else None,
            final_score=fused.final_score if fused else None,
            conflict=fused.conflict if fused else None,
            decision=fused.decision if fused else None,
            reason_summary=fused.reason_summary if fused else None,
            branches=fused.branches if fused else None,
        ) if fused else None,
        created_at=document.created_at,
    )


@router.post("/{doc_id}/feedback")
async def submit_feedback(doc_id: str, body: FeedbackRequest, db: Session = Depends(get_db)):
    """Record a reviewer's ground-truth label for a verification.

    This is the supervision signal the reliability calibrator learns from. Only
    trusted, human-confirmed labels should reach this endpoint -- never raw,
    attacker-influenced inputs (online learning is a poisoning surface).
    """
    if body.true_label not in ("authentic", "forged"):
        raise HTTPException(status_code=400, detail="true_label must be 'authentic' or 'forged'")

    job = db.query(VerificationJob).filter(VerificationJob.document_id == doc_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")

    feedback = ReviewFeedback(
        job_id=job.id,
        document_id=doc_id,
        true_label=body.true_label,
        reviewer=body.reviewer,
        notes=body.notes,
    )
    db.add(feedback)
    db.commit()
    return {"status": "recorded", "job_id": job.id, "true_label": body.true_label}


@router.get("/{doc_id}/audit")
async def get_audit_trail(doc_id: str, db: Session = Depends(get_db)):
    from app.models.models import AuditLog
    job = db.query(VerificationJob).filter(VerificationJob.document_id == doc_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")

    audit = db.query(AuditLog).filter(AuditLog.job_id == job.id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")

    return {
        "id": audit.id,
        "document_hash": audit.document_hash,
        "verification_timestamp": audit.verification_timestamp,
        "verification_status": audit.verification_status,
        "authenticity_score": audit.authenticity_score,
        "previous_hash": audit.previous_hash,
        "block_hash": audit.block_hash,
    }


def _run_verification_pipeline(file_path: str, job_id: str, db: Session):
    # Layout detection runs first so its field crops can guide OCR. Image-only;
    # degrades to a vacuous belief on PDFs or when the model/deps are missing.
    layout_result = layout_service.analyze(file_path)

    ocr_result = ocr_service.extract_text(
        file_path, regions=layout_result.get("detections"),
    )
    ocr_db = OCRResult(
        job_id=job_id,
        raw_text=ocr_result["raw_text"],
        extracted_fields=ocr_result["extracted_fields"],
        confidence=ocr_result["confidence"],
    )
    db.add(ocr_db)

    semantic_result = semantic_validator.validate(ocr_result["extracted_fields"])
    semantic_db = SemanticResult(
        job_id=job_id,
        aadhaar_valid=semantic_result["aadhaar_valid"],
        pan_valid=semantic_result["pan_valid"],
        dates_valid=semantic_result["dates_valid"],
        field_presence_valid=semantic_result["field_presence_valid"],
        consistency_score=semantic_result["consistency_score"],
        validation_details=semantic_result["validation_details"],
    )
    db.add(semantic_db)

    vision_result = vision_service.analyze(file_path)
    vision_db = VisionResult(
        job_id=job_id,
        tamper_probability=vision_result["tamper_probability"],
        confidence=vision_result["confidence"],
        heatmap_path=vision_result["heatmap_path"],
        explanation=vision_result["explanation"],
    )
    db.add(vision_db)

    signature_result = signature_service.verify(file_path)
    signature_db = SignatureResult(
        job_id=job_id,
        signature_detected=signature_result["signature_detected"],
        certificate_valid=signature_result["certificate_valid"],
        hash_valid=signature_result["hash_valid"],
        validation_result=signature_result["validation_result"],
        details=signature_result["details"],
    )
    db.add(signature_db)

    # Secure-QR branch cross-checks the (now layout-guided) OCR fields against
    # the tamper-proof signed QR. Image-only; vacuous on PDFs / when absent.
    qr_result = aadhaar_qr_service.analyze(
        file_path,
        ocr_fields=ocr_result["extracted_fields"],
        uidai_cert_path=os.getenv("MDAV_UIDAI_CERT"),
    )

    # AIForge diffusion / AI-generated-forgery branch (placeholder until the
    # teammate's model lands -- emits a vacuous belief in the meantime).
    diffusion_result = diffusion_service.analyze(file_path)

    # Each branch contributes a Dempster-Shafer BeliefMass; fusion discounts by
    # source reliability and combines them.
    branch_masses = {
        "visual": vision_result.get("_mass"),
        "semantic": semantic_validator.to_belief(semantic_result),
        "signature": _signature_belief(signature_result),
        "qr": qr_result.get("_mass"),
        "layout": layout_result.get("_mass"),
        "diffusion": diffusion_result.get("_mass"),
    }
    fused_result = fusion_service.fuse(branch_masses)

    # Per-branch payload for the frontend: score + belief + branch-specific
    # detail, rendered generically so new branches need no UI changes.
    branches_payload = _build_branches_payload(
        fused_result, vision_result, semantic_result, signature_result,
        qr_result, layout_result, diffusion_result,
    )

    fused_db = FusedResult(
        job_id=job_id,
        visual_score=fused_result["visual_score"],
        semantic_score=fused_result["semantic_score"],
        signature_score=fused_result["signature_score"],
        layout_score=fused_result["layout_score"],
        qr_score=fused_result["qr_score"],
        diffusion_score=fused_result["diffusion_score"],
        final_score=fused_result["final_score"],
        conflict=fused_result["conflict"],
        decision=fused_result["decision"],
        reason_summary=fused_result["reason_summary"],
        branches=branches_payload,
    )
    db.add(fused_db)

    db.commit()

    audit_service.create_audit_record(job_id, file_path, {**fused_result, "branches": branches_payload}, db)


def _build_branches_payload(fused, vision, semantic, signature, qr, layout, diffusion) -> dict:
    """Assemble each branch's score + belief + display detail for the UI."""
    return {
        "visual": {
            "label": "Visual Forensics (DocTamper)",
            "score": fused["visual_score"],
            "belief": vision.get("belief"),
            "status": "mock" if vision.get("mock") else "active",
            "detail": {
                "tamper_probability": vision.get("tamper_probability"),
                "confidence": vision.get("confidence"),
                "heatmap_path": vision.get("heatmap_path"),
                "explanation": vision.get("explanation"),
            },
        },
        "semantic": {
            "label": "OCR & Semantic",
            "score": fused["semantic_score"],
            "belief": semantic_validator.to_belief(semantic).to_dict(),
            "status": "active",
            "detail": {"consistency_score": semantic.get("consistency_score")},
        },
        "signature": {
            "label": "Digital Signature",
            "score": fused["signature_score"],
            "belief": _signature_belief(signature).to_dict(),
            "status": "active" if signature.get("signature_detected") else "inactive",
            "detail": {"validation_result": signature.get("validation_result")},
        },
        "qr": {
            "label": "Aadhaar Secure QR",
            "score": fused["qr_score"],
            "belief": qr.get("belief"),
            "status": "active" if qr.get("qr_found") else "inactive",
            "detail": {
                "qr_found": qr.get("qr_found", False),
                "mismatches": qr.get("mismatches", []),
                "signature_status": qr.get("signature_status"),
            },
        },
        "layout": {
            "label": "Layout Detection (YOLO)",
            "score": fused["layout_score"],
            "belief": layout.get("belief"),
            "status": "mock" if layout.get("mock") else "active",
            "detail": {"fields_detected": layout.get("fields_detected", [])},
        },
        "diffusion": {
            "label": "AI/Diffusion Forgery (AIForge)",
            "score": fused["diffusion_score"],
            "belief": diffusion.get("belief"),
            "status": diffusion.get("status", "pending"),
            "detail": {
                "ai_forgery_prob": diffusion.get("ai_forgery_prob"),
                "reason": diffusion.get("reason"),
            },
        },
    }


def _signature_belief(signature_result: dict):
    """Map a signature verification result to a BeliefMass.

    A cryptographically VALID signature is strong authentic evidence; an INVALID
    one (tampered content / broken chain) is near-conclusive forgery evidence.
    No signature / not-applicable / error -> vacuous (PDFs without a signature
    and all images legitimately have nothing to say here).
    """
    result = signature_result.get("validation_result")
    if result == "VALID":
        return from_check(True, w_pass=0.90, source="signature",
                          details={"validation_result": result})
    if result == "INVALID":
        return from_check(False, w_fail=0.95, source="signature",
                          details={"validation_result": result})
    return vacuous(source="signature")


def _detect_doc_type(filename: str) -> str:
    filename_lower = filename.lower()
    if "aadhaar" in filename_lower or "aadhar" in filename_lower:
        return "aadhaar"
    elif "pan" in filename_lower:
        return "pan"
    elif "passport" in filename_lower:
        return "passport"
    elif "license" in filename_lower or "licence" in filename_lower:
        return "license"
    else:
        return "other"
