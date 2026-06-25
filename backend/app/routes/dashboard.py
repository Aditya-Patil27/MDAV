from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.models import Document, VerificationJob, FusedResult
from app.models.schemas import DashboardStats, HistoryItem

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: Session = Depends(get_db)):
    total_docs = db.query(func.count(Document.id)).scalar()
    total_jobs = db.query(func.count(VerificationJob.id)).scalar()

    approved = (
        db.query(func.count(FusedResult.id))
        .filter(FusedResult.decision == "APPROVED")
        .scalar()
    )
    flagged = (
        db.query(func.count(FusedResult.id))
        .filter(FusedResult.decision == "FLAGGED")
        .scalar()
    )
    review = (
        db.query(func.count(FusedResult.id))
        .filter(FusedResult.decision == "REVIEW_REQUIRED")
        .scalar()
    )

    return DashboardStats(
        total_documents=total_docs,
        total_verifications=total_jobs,
        approved_count=approved,
        flagged_count=flagged,
        review_required_count=review,
    )


@router.get("/recent", response_model=list[HistoryItem])
async def get_recent(db: Session = Depends(get_db)):
    recent_jobs = (
        db.query(VerificationJob, Document, FusedResult)
        .join(Document, VerificationJob.document_id == Document.id)
        .outerjoin(FusedResult, VerificationJob.id == FusedResult.job_id)
        .order_by(VerificationJob.created_at.desc())
        .limit(10)
        .all()
    )

    results = []
    for job, doc, fused in recent_jobs:
        results.append(
            HistoryItem(
                document_id=doc.id,
                filename=doc.filename,
                doc_type=doc.doc_type,
                decision=fused.decision if fused else None,
                final_score=fused.final_score if fused else None,
                created_at=job.created_at,
            )
        )

    return results
