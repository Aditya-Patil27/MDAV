import asyncio
from datetime import datetime

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import AuditLog, Document, FusedResult, VerificationJob
from app.routes.dashboard import get_history, get_stats
from app.routes.documents import (
    _signature_belief,
    get_audit_trail,
    get_document_results,
)
from app.services.aadhaar_qr import AadhaarQRService
from app.services.document_context import infer_document_context
from app.services.layout_service import LayoutService
from app.services.semantic_service import SemanticValidator
from app.services.signature_service import SignatureService
from app.services.vision_service import VisionService


def test_unavailable_visual_model_is_vacuous_without_fake_probability(tmp_path):
    service = VisionService(model_path=str(tmp_path / "missing.pth"))
    result = service.analyze(str(tmp_path / "synthetic.png"))
    assert result["status"] == "unavailable"
    assert result["tamper_probability"] is None
    assert result["confidence"] == 0.0
    assert result["belief"]["uncertain"] == 1.0


def test_subthreshold_visual_map_is_inconclusive_not_forged_evidence(tmp_path):
    service = VisionService(model_path=str(tmp_path / "missing.pth"))
    service._last_valid = (100, 100)
    probability, confidence, area = service._aggregate(
        np.full((100, 100), 0.79, dtype=np.float32)
    )
    assert probability == 0.0
    assert confidence == 0.0
    assert area == 0.0
    assert service._last_prediction_details["positive_region_detected"] is False


def test_jpg_signature_is_not_applicable_and_vacuous():
    result = SignatureService().verify("synthetic.jpg")
    assert result["validation_result"] == "NOT_APPLICABLE"
    assert result["certificate_valid"] is None
    assert _signature_belief(result).uncertain == 1.0


def test_absent_qr_contributes_no_forged_evidence(monkeypatch):
    service = AadhaarQRService()
    monkeypatch.setattr(service, "decode_qr_from_image", lambda _: None)
    result = service.analyze("synthetic-aadhaar-front.png")
    assert result["qr_found"] is False
    assert result["belief"]["forged"] == 0.0
    assert result["belief"]["uncertain"] == 1.0


def test_ocr_fallback_identifies_aadhaar_front_without_layout():
    context = infer_document_context(
        filename="synthetic.png",
        raw_text="Government of India\nDOB: 01/01/2000\n1234 5678 9012",
        extracted_fields={"aadhaar": "123456789012", "dates": ["01/01/2000"]},
        layout_result={"mock": True, "fields_detected": []},
    )
    assert context.document_type == "aadhaar"
    assert context.side == "front"
    assert context.source == "ocr"


def test_aadhaar_front_does_not_require_back_side_address():
    validator = SemanticValidator()
    result = validator.validate(
        {"aadhaar": "123456789012", "name": "SYNTHETIC USER", "dates": ["01/01/2000"]},
        document_type="aadhaar",
        document_side="front",
        document_type_confidence=0.9,
        ocr_confidence=0.9,
        layout_available=True,
    )
    detail = result["validation_details"]["field_presence"]
    assert "address" not in detail["expected_fields"]
    assert result["field_presence_valid"] is True


def test_unknown_type_with_offline_layout_does_not_fail_required_fields():
    result = SemanticValidator().validate(
        {},
        document_type="unknown",
        document_side="unknown",
        document_type_confidence=0.0,
        ocr_confidence=0.2,
        layout_available=False,
    )
    assert result["field_presence_valid"] is None
    assert result["validation_details"]["field_presence"]["status"] == "not_evaluated"


def test_missing_aadhaar_front_fields_are_inconclusive_not_invalid():
    result = SemanticValidator().validate(
        {"aadhaar": "123456789012"},
        document_type="aadhaar",
        document_side="front",
        document_type_confidence=0.9,
        ocr_confidence=0.95,
        layout_available=True,
        field_evidence={
            "aadhaar": {"source": "layout_crop", "text_found": True},
        },
    )
    detail = result["validation_details"]["field_presence"]
    assert result["field_presence_valid"] is None
    assert detail["status"] == "not_evaluated"
    assert detail["missing_fields"] == ["dates", "name"]


def test_pan_identifier_beats_a_lone_aadhaar_layout_box():
    context = infer_document_context(
        filename="identity.png",
        raw_text="INCOME TAX DEPARTMENT\nABCDE1234F",
        extracted_fields={"pan": "ABCDE1234F"},
        layout_result={"mock": False, "fields_detected": ["aadhaar_number"]},
    )
    assert context.document_type == "pan"
    assert context.source == "ocr"


def test_aadhaar_layout_contributes_vacuous_evidence_for_pan():
    service = LayoutService(model_path="missing-layout-model.pt")
    raw_result = {
        "detections": [{"label": "aadhaar_number", "confidence": 0.9}],
        "fields_detected": ["aadhaar_number"],
        "mock": False,
    }
    result = service.for_document_context(raw_result, "pan")
    assert result["status"] == "not_applicable"
    assert result["fields_detected"] == []
    assert result["_mass"].uncertain == 1.0


def test_dashboard_counts_review_and_score_is_consistent_across_views():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    now = datetime.utcnow()
    try:
        for index in range(3):
            doc_id = f"doc-{index}"
            job_id = f"job-{index}"
            session.add(Document(
                id=doc_id,
                filename=f"synthetic-{index}.png",
                file_type=".png",
                file_size=10,
                storage_path=f"/tmp/{doc_id}.png",
                doc_type="unknown",
                created_at=now,
            ))
            session.add(VerificationJob(
                id=job_id,
                document_id=doc_id,
                status="completed",
                created_at=now,
                completed_at=now,
            ))
            session.add(FusedResult(
                id=f"fused-{index}",
                job_id=job_id,
                final_score=0.445,
                conflict=0.12,
                decision="REVIEW_REQUIRED",
                branches={},
            ))
            session.add(AuditLog(
                id=f"audit-{index}",
                job_id=job_id,
                authenticity_score=0.445,
                verification_status="REVIEW_REQUIRED",
                verification_timestamp=now,
                details={
                    "decision_score": 0.445,
                    "score_formula": "pignistic_authenticity_v1",
                    "fused_belief": {
                        "authentic": 0.31,
                        "forged": 0.42,
                        "uncertain": 0.27,
                    },
                },
            ))
        session.commit()

        stats = asyncio.run(get_stats(session))
        assert stats.total_verifications == 3
        assert stats.review_required_count == 3
        assert stats.approved_count == 0
        assert stats.flagged_count == 0

        history = asyncio.run(get_history(
            search=None,
            decision=None,
            doc_type=None,
            date_from=None,
            date_to=None,
            sort="date_desc",
            page=1,
            page_size=10,
            db=session,
        ))
        result = asyncio.run(get_document_results("doc-0", session))
        audit = asyncio.run(get_audit_trail("doc-0", session))
        assert history.items[0].final_score == 0.445
        assert result.fused.decision_score == 0.445
        assert audit["authenticity_score"] == 0.445
    finally:
        session.close()
