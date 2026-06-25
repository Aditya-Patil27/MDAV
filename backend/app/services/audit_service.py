from datetime import datetime
from app.utils.hash_utils import compute_file_hash, compute_data_hash, compute_block_hash


class AuditService:
    def __init__(self):
        self.last_hash = "0" * 64

    def create_audit_record(self, job_id: str, document_path: str, verification_data: dict, db_session) -> dict:
        from app.models.models import AuditLog

        document_hash = compute_file_hash(document_path)

        timestamp = datetime.utcnow().isoformat()
        data_hash = compute_data_hash(verification_data)
        block_hash = compute_block_hash(self.last_hash, data_hash, timestamp)

        audit_log = AuditLog(
            job_id=job_id,
            document_hash=document_hash,
            verification_timestamp=datetime.utcnow(),
            verification_status=verification_data.get("decision", "UNKNOWN"),
            authenticity_score=verification_data.get("final_score", 0.0),
            previous_hash=self.last_hash,
            block_hash=block_hash,
            details=verification_data,
        )

        db_session.add(audit_log)
        db_session.commit()

        self.last_hash = block_hash

        return {
            "id": audit_log.id,
            "document_hash": document_hash,
            "verification_timestamp": audit_log.verification_timestamp,
            "verification_status": audit_log.verification_status,
            "authenticity_score": audit_log.authenticity_score,
            "block_hash": block_hash,
        }


audit_service = AuditService()
