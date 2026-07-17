import math
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    AuditLog,
    Document,
    FusedResult,
    SemanticResult,
    VerificationJob,
)
from app.models.schemas import DashboardStats, HistoryItem, HistoryPage

router = APIRouter()

DECISIONS = {"APPROVED", "REVIEW_REQUIRED", "FLAGGED"}


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: Session = Depends(get_db)):
    total_docs = db.query(func.count(Document.id)).scalar() or 0
    outcome_counts = {
        decision: (
            db.query(func.count(FusedResult.id))
            .filter(FusedResult.decision == decision)
            .scalar()
            or 0
        )
        for decision in DECISIONS
    }
    total_verifications = sum(outcome_counts.values())

    rows = (
        db.query(FusedResult, VerificationJob, AuditLog)
        .join(VerificationJob, FusedResult.job_id == VerificationJob.id)
        .outerjoin(AuditLog, AuditLog.job_id == VerificationJob.id)
        .all()
    )
    uncertainties = []
    conflicts = []
    availability: dict[str, dict[str, int]] = {}
    today = date.today()
    activity_days = [today - timedelta(days=offset) for offset in range(13, -1, -1)]
    activity_map = {
        day: {"approved": 0, "review_required": 0, "flagged": 0}
        for day in activity_days
    }
    last_seven = 0

    for fused, job, audit in rows:
        summary = _fusion_summary(audit)
        uncertainty = summary.get("uncertainty_mass")
        if uncertainty is not None:
            uncertainties.append(float(uncertainty))
        if fused.conflict is not None:
            conflicts.append(float(fused.conflict))

        for source, branch in (fused.branches or {}).items():
            if not isinstance(branch, dict):
                continue
            bucket = availability.setdefault(source, {"active": 0, "total": 0})
            bucket["total"] += 1
            if branch.get("status") == "active":
                bucket["active"] += 1

        verified_at = job.completed_at or job.created_at
        if verified_at:
            day = verified_at.date()
            if day in activity_map and fused.decision in DECISIONS:
                activity_map[day][fused.decision.lower()] += 1
            if day >= today - timedelta(days=6):
                last_seven += 1

    branch_availability = {
        source: {
            **counts,
            "rate": round(counts["active"] / counts["total"], 4)
            if counts["total"]
            else 0.0,
        }
        for source, counts in availability.items()
    }
    activity = [
        {"date": day.isoformat(), **activity_map[day]} for day in activity_days
    ]

    return DashboardStats(
        total_documents=total_docs,
        total_verifications=total_verifications,
        approved_count=outcome_counts["APPROVED"],
        flagged_count=outcome_counts["FLAGGED"],
        review_required_count=outcome_counts["REVIEW_REQUIRED"],
        average_uncertainty=(
            round(sum(uncertainties) / len(uncertainties), 4)
            if uncertainties
            else None
        ),
        average_conflict=(
            round(sum(conflicts) / len(conflicts), 4) if conflicts else None
        ),
        verifications_last_7_days=last_seven,
        activity=activity,
        branch_availability=branch_availability,
    )


@router.get("/history", response_model=HistoryPage)
async def get_history(
    search: str | None = None,
    decision: str | None = None,
    doc_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = Query("date_desc", pattern="^(date|score)_(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(VerificationJob, Document, FusedResult, SemanticResult, AuditLog)
        .join(Document, VerificationJob.document_id == Document.id)
        .join(FusedResult, VerificationJob.id == FusedResult.job_id)
        .outerjoin(SemanticResult, VerificationJob.id == SemanticResult.job_id)
        .outerjoin(AuditLog, VerificationJob.id == AuditLog.job_id)
    )

    if search:
        query = query.filter(Document.filename.ilike(f"%{search.strip()}%"))
    if decision and decision.upper() in DECISIONS:
        query = query.filter(FusedResult.decision == decision.upper())
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    verified_at = func.coalesce(VerificationJob.completed_at, VerificationJob.created_at)
    if date_from:
        query = query.filter(verified_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(verified_at <= datetime.combine(date_to, time.max))

    sort_column = (
        func.coalesce(AuditLog.authenticity_score, FusedResult.final_score)
        if sort.startswith("score")
        else verified_at
    )
    query = query.order_by(sort_column.asc() if sort.endswith("asc") else sort_column.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_history_item(*row) for row in rows]
    return HistoryPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/recent", response_model=list[HistoryItem])
async def get_recent(db: Session = Depends(get_db)):
    """Compatibility endpoint for existing clients; returns the newest ten."""
    rows = (
        db.query(VerificationJob, Document, FusedResult, SemanticResult, AuditLog)
        .join(Document, VerificationJob.document_id == Document.id)
        .join(FusedResult, VerificationJob.id == FusedResult.job_id)
        .outerjoin(SemanticResult, VerificationJob.id == SemanticResult.job_id)
        .outerjoin(AuditLog, VerificationJob.id == AuditLog.job_id)
        .order_by(VerificationJob.created_at.desc())
        .limit(10)
        .all()
    )
    return [_history_item(*row) for row in rows]


def _history_item(job, document, fused, semantic, audit) -> HistoryItem:
    context = (
        (semantic.validation_details or {}).get("document_context", {})
        if semantic
        else {}
    )
    summary = _fusion_summary(audit)
    branches = fused.branches if fused and isinstance(fused.branches, dict) else {}
    active = sum(
        1 for branch in branches.values()
        if isinstance(branch, dict) and branch.get("status") == "active"
    )
    total = sum(1 for branch in branches.values() if isinstance(branch, dict))
    return HistoryItem(
        document_id=document.id,
        filename=document.filename,
        doc_type=context.get("document_type") or document.doc_type or "unknown",
        doc_side=context.get("side", "unknown"),
        doc_type_confidence=context.get("confidence"),
        doc_type_source=context.get("source", "unknown"),
        decision=fused.decision if fused else None,
        final_score=(
            summary.get("decision_score", fused.final_score) if fused else None
        ),
        uncertainty=summary.get("uncertainty_mass"),
        conflict=fused.conflict if fused else None,
        active_branches=active,
        total_branches=total,
        created_at=job.completed_at or job.created_at,
    )


def _fusion_summary(audit: AuditLog | None) -> dict:
    if not audit or not isinstance(audit.details, dict):
        return {}
    belief = audit.details.get("fused_belief") or {}
    return {
        "decision_score": audit.details.get(
            "decision_score", audit.authenticity_score
        ),
        "authentic_mass": audit.details.get("authentic_mass", belief.get("authentic")),
        "forged_mass": audit.details.get("forged_mass", belief.get("forged")),
        "uncertainty_mass": audit.details.get(
            "uncertainty_mass", belief.get("uncertain")
        ),
    }
