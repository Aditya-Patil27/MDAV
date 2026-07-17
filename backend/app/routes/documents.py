from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import os
import uuid

from app.database import get_db
from app.models.models import (
    AuditLog,
    Document,
    VerificationJob,
    OCRResult,
    SemanticResult,
    VisionResult,
    SignatureResult,
    FusedResult,
    ReviewFeedback,
)
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
from app.services.belief import BeliefMass, from_check, vacuous
from app.services.document_context import infer_document_context
from app.services.fusion_service import RELIABILITY, SCORE_FORMULA, THRESHOLDS

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
    audit = db.query(AuditLog).filter(AuditLog.job_id == job.id).first()
    semantic_details = semantic.validation_details if semantic else {}
    document_context = (semantic_details or {}).get("document_context", {})
    stored_fusion = audit.details if audit and isinstance(audit.details, dict) else {}
    fused_belief = stored_fusion.get("fused_belief", {})

    return VerificationResultResponse(
        document_id=doc_id,
        filename=document.filename,
        doc_type=document_context.get("document_type") or document.doc_type or "unknown",
        doc_side=document_context.get("side", "unknown"),
        doc_type_confidence=document_context.get("confidence"),
        doc_type_source=document_context.get("source", "unknown"),
        possible_doc_type=document_context.get("possible_type"),
        preview_url=f"/files/{os.path.basename(document.storage_path)}",
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
            status=_semantic_status(semantic.validation_details if semantic else None),
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
            decision_score=(
                stored_fusion.get("decision_score", fused.final_score)
                if fused else None
            ),
            score_formula=stored_fusion.get("score_formula", SCORE_FORMULA),
            authentic_mass=stored_fusion.get(
                "authentic_mass", fused_belief.get("authentic")
            ),
            forged_mass=stored_fusion.get(
                "forged_mass", fused_belief.get("forged")
            ),
            uncertainty_mass=stored_fusion.get(
                "uncertainty_mass", fused_belief.get("uncertain")
            ),
            conflict=fused.conflict if fused else None,
            decision=fused.decision if fused else None,
            reason_summary=fused.reason_summary if fused else None,
            branches=(
                _normalize_stored_branches(fused.branches, document_context)
                if fused else None
            ),
            decision_thresholds=stored_fusion.get(
                "decision_thresholds", dict(THRESHOLDS)
            ),
        ) if fused else None,
        created_at=document.created_at,
        verified_at=job.completed_at or job.created_at,
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
        "score_formula": (
            audit.details.get("score_formula", SCORE_FORMULA)
            if isinstance(audit.details, dict)
            else SCORE_FORMULA
        ),
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

    job = db.query(VerificationJob).filter(VerificationJob.id == job_id).first()
    document = job.document if job else None
    document_context = infer_document_context(
        filename=document.filename if document else os.path.basename(file_path),
        raw_text=ocr_result.get("raw_text", ""),
        extracted_fields=ocr_result.get("extracted_fields", {}),
        layout_result=layout_result,
    )
    if document is not None:
        document.doc_type = document_context.document_type

    # The detector supplies Aadhaar crops to OCR, but its structural belief is
    # not valid evidence after OCR establishes a different document type.
    layout_evidence = layout_service.for_document_context(
        layout_result, document_context.document_type
    )

    semantic_result = semantic_validator.validate(
        ocr_result["extracted_fields"],
        document_type=document_context.document_type,
        document_side=document_context.side,
        document_type_confidence=document_context.confidence,
        ocr_confidence=ocr_result.get("confidence", 0.0),
        layout_available=layout_evidence.get("status") == "active",
        field_evidence=ocr_result.get("field_evidence"),
    )
    semantic_result["validation_details"]["document_context"] = {
        **document_context.to_dict(),
        "layout_available": layout_evidence.get("status") == "active",
        "ocr_confidence": round(float(ocr_result.get("confidence", 0.0)), 4),
    }
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

    vision_result = vision_service.analyze(
        file_path, document_type=document_context.document_type
    )
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

    # AIForge diffusion / AI-generated-forgery segmentation branch. It emits
    # vacuous belief when its checkpoint or optional ML dependencies are absent.
    diffusion_result = diffusion_service.analyze(
        file_path, document_type=document_context.document_type
    )

    # Each branch contributes a Dempster-Shafer BeliefMass; fusion discounts by
    # source reliability and combines them.
    branch_masses = {
        "visual": vision_result.get("_mass"),
        "semantic": semantic_validator.to_belief(semantic_result),
        "signature": _signature_belief(signature_result),
        "qr": qr_result.get("_mass"),
        "layout": layout_evidence.get("_mass"),
        "diffusion": diffusion_result.get("_mass"),
    }
    branch_metadata = _build_branch_metadata(
        file_path=file_path,
        document_context=document_context.to_dict(),
        vision=vision_result,
        semantic=semantic_result,
        signature=signature_result,
        qr=qr_result,
        layout=layout_evidence,
        diffusion=diffusion_result,
    )
    fused_result = fusion_service.fuse(branch_masses, branch_metadata)

    # Per-branch payload for the frontend: score + belief + branch-specific
    # detail, rendered generically so new branches need no UI changes.
    branches_payload = _build_branches_payload(
        fused_result, vision_result, semantic_result, signature_result,
        qr_result, layout_evidence, diffusion_result, branch_metadata,
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


def _build_branches_payload(
    fused, vision, semantic, signature, qr, layout, diffusion, metadata
) -> dict:
    """Build the normalized raw-versus-discounted branch evidence contract.

    ``belief`` intentionally remains the raw mass for calibration compatibility.
    ``mass`` is the reliability-discounted mass shown to users and combined by
    fusion, preventing callers from discounting the same source twice.
    """
    labels = {
        "visual": "Conventional visual forensics",
        "semantic": "OCR and semantic validation",
        "signature": "PDF digital signature",
        "qr": "Aadhaar Secure QR",
        "layout": "Document layout detection",
        "diffusion": "AI-generated forgery localization",
    }
    raw_results = {
        "visual": vision,
        "semantic": semantic,
        "signature": signature,
        "qr": qr,
        "layout": layout,
        "diffusion": diffusion,
    }
    probabilities = {
        "visual": (vision.get("tamper_probability"), "tampering"),
        "diffusion": (diffusion.get("ai_forgery_prob"), "forgery"),
    }
    details = {
        "visual": {
            "heatmap_path": vision.get("heatmap_path"),
            "explanation": vision.get("explanation"),
        },
        "semantic": {
            "consistency_score": semantic.get("consistency_score"),
            "rule_statuses": semantic.get("validation_details", {}).get(
                "rule_statuses", {}
            ),
            "document_context": semantic.get("validation_details", {}).get(
                "document_context", {}
            ),
        },
        "signature": {
            "validation_result": signature.get("validation_result"),
            **(signature.get("details") or {}),
        },
        "qr": {
            "qr_found": qr.get("qr_found", False),
            "mismatches": qr.get("mismatches", []),
            "signature_status": qr.get("signature_status"),
        },
        "layout": {
            "fields_detected": layout.get("fields_detected", []),
        },
        "diffusion": {
            **(diffusion.get("details") or {}),
            "model_limitation": (
                "Validated primarily on receipt/form-derived edits; identity-document "
                "predictions require human review."
            ),
        },
    }

    payload = {}
    for source, result in raw_results.items():
        evidence = fused.get("branch_evidence", {}).get(source, {})
        probability, probability_label = probabilities.get(source, (None, None))
        confidence = result.get("confidence")
        if confidence is None and evidence.get("raw_mass"):
            confidence = 1.0 - evidence["raw_mass"].get("uncertain", 1.0)
        payload[source] = {
            "branch": source,
            "display_name": labels[source],
            "label": labels[source],
            "status": metadata[source]["status"],
            "applicable": metadata[source]["applicable"],
            "raw_probability": probability,
            "probability_label": probability_label,
            "confidence": confidence,
            "reliability": evidence.get("reliability"),
            "raw_mass": evidence.get("raw_mass"),
            "belief": evidence.get("raw_mass"),
            "mass": evidence.get("discounted_mass"),
            "score": evidence.get("discounted_pignistic_authenticity"),
            "raw_score": evidence.get("raw_pignistic_authenticity"),
            "score_label": "discounted_pignistic_authenticity",
            "reason": metadata[source]["reason"],
            "detail": details[source],
        }
    return payload


def _build_branch_metadata(
    *, file_path, document_context, vision, semantic, signature, qr, layout, diffusion
) -> dict:
    signature_result = signature.get("validation_result")
    if signature_result == "NOT_APPLICABLE":
        signature_status = "not_applicable"
        signature_reason = (
            "Embedded PDF signature verification applies only to supported PDF inputs."
        )
    elif signature_result == "ERROR":
        signature_status = "error"
        signature_reason = signature.get("details", {}).get(
            "error", "Signature verification could not run."
        )
    elif signature_result == "NO_SIGNATURE":
        signature_status = "inconclusive"
        signature_reason = "No embedded signature was detected in the PDF."
    else:
        signature_status = "active"
        signature_reason = f"Signature verification result: {signature_result}."

    doc_type = document_context.get("document_type", "unknown")
    doc_side = document_context.get("side", "unknown")
    if qr.get("qr_found"):
        qr_status = "active"
        qr_reason = qr.get("reason", "Secure QR evidence was evaluated.")
    elif doc_type != "aadhaar":
        qr_status = "not_applicable"
        qr_reason = "Aadhaar Secure QR validation is not applicable to this document type."
    elif doc_side == "front":
        qr_status = "not_applicable"
        qr_reason = (
            "QR not present in the submitted Aadhaar front side; no QR evidence contributed."
        )
    else:
        qr_status = "inconclusive"
        qr_reason = "No decodable Secure QR was present; the branch contributed no evidence."

    image_input = not file_path.lower().endswith(".pdf")
    if not image_input:
        layout_status = "not_applicable"
    else:
        layout_status = layout.get("status")
        if not layout_status:
            layout_status = "unavailable" if layout.get("mock") else (
                "active" if layout.get("fields_detected") else "inconclusive"
            )

    diffusion_status = diffusion.get("status", "pending")
    if diffusion_status == "pending":
        diffusion_status = "unavailable"

    return {
        "visual": {
            "status": vision.get("status", "unavailable" if vision.get("mock") else "active"),
            "applicable": True,
            "reason": vision.get("explanation", "Visual evidence was not available."),
        },
        "semantic": {
            "status": semantic.get("status", "inconclusive"),
            "applicable": True,
            "reason": _semantic_reason(semantic),
        },
        "signature": {
            "status": signature_status,
            "applicable": signature_status != "not_applicable",
            "reason": signature_reason,
        },
        "qr": {
            "status": qr_status,
            "applicable": qr_status != "not_applicable",
            "reason": qr_reason,
        },
        "layout": {
            "status": layout_status,
            "applicable": image_input and layout_status != "not_applicable",
            "reason": (
                layout.get("reason", "Layout evidence was not available.")
                if image_input
                else "Image layout detection is not applied directly to PDF inputs."
            ),
        },
        "diffusion": {
            "status": diffusion_status,
            "applicable": True,
            "reason": diffusion.get("reason", "AI-forgery evidence was not available."),
        },
    }


def _semantic_reason(semantic: dict) -> str:
    field_info = semantic.get("validation_details", {}).get("field_presence", {})
    if field_info.get("status") == "not_evaluated":
        return field_info.get("reason", "Required-field rules were not evaluated.")
    return "Applicable OCR consistency and semantic rules were evaluated."


def _semantic_status(validation_details: dict | None) -> str:
    statuses = (validation_details or {}).get("rule_statuses", {}).values()
    return "active" if any(status in {"valid", "invalid"} for status in statuses) else "inconclusive"


def _normalize_stored_branches(branches: dict | None, document_context: dict) -> dict:
    """Upgrade legacy branch JSON at read time without a database migration."""
    normalized = {}
    for source, stored in (branches or {}).items():
        if not isinstance(stored, dict):
            continue
        item = dict(stored)
        detail = dict(item.get("detail") or {})
        raw_mass = item.get("raw_mass") or item.get("belief")
        reliability = item.get("reliability", RELIABILITY.get(source, 0.5))
        discounted_mass = item.get("mass")
        if raw_mass and not discounted_mass:
            try:
                discounted_mass = BeliefMass(
                    authentic=float(raw_mass["authentic"]),
                    forged=float(raw_mass["forged"]),
                    uncertain=float(raw_mass["uncertain"]),
                    source=source,
                ).discount(float(reliability)).to_dict()
            except (KeyError, TypeError, ValueError):
                discounted_mass = None

        status = item.get("status", "inconclusive")
        if status in {"mock", "pending"}:
            status = "unavailable"
        elif status == "inactive":
            if source == "signature" and detail.get("validation_result") == "NOT_APPLICABLE":
                status = "not_applicable"
            elif source == "qr" and (
                document_context.get("document_type") != "aadhaar"
                or document_context.get("side") == "front"
            ):
                status = "not_applicable"
            else:
                status = "inconclusive"

        if source == "visual" and status == "unavailable":
            detail["tamper_probability"] = None

        raw_probability = item.get("raw_probability")
        probability_label = item.get("probability_label")
        if raw_probability is None and status == "active":
            if source == "visual":
                raw_probability = detail.get("tamper_probability")
                probability_label = "tampering"
            elif source == "diffusion":
                raw_probability = detail.get("ai_forgery_prob")
                probability_label = "forgery"

        confidence = item.get("confidence")
        if confidence is None:
            confidence = detail.get("confidence")
        if confidence is None and raw_mass:
            confidence = 1.0 - float(raw_mass.get("uncertain", 1.0))

        if status == "not_applicable":
            applicable = False
        else:
            applicable = item.get("applicable", True)
        score = item.get("score")
        if discounted_mass and item.get("score_label") != "discounted_pignistic_authenticity":
            score = float(discounted_mass.get("authentic", 0.0)) + 0.5 * float(
                discounted_mass.get("uncertain", 1.0)
            )

        normalized[source] = {
            **item,
            "branch": source,
            "display_name": item.get("display_name") or item.get("label") or source,
            "status": status,
            "applicable": applicable,
            "raw_probability": raw_probability,
            "probability_label": probability_label,
            "confidence": confidence,
            "reliability": reliability,
            "raw_mass": raw_mass,
            "belief": raw_mass,
            "mass": discounted_mass,
            "score": score,
            "score_label": "discounted_pignistic_authenticity",
            "detail": detail,
        }
    return normalized


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
        return "driving_licence"
    else:
        return "unknown"
