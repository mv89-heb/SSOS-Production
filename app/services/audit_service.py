from datetime import datetime, timezone

from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog, GENESIS_HASH, compute_hash
from app.models.tenant import Tenant
from app.repositories.audit_repository import AuditRepository


class AuditService:
    @staticmethod
    def log_event(tenant_id: int, user_id, action: str, title: str = "", metadata: dict = None) -> AuditLog:
        # Serialize audit writers per tenant. PostgreSQL row-level locking makes
        # concurrent requests wait for the previous writer, so two events can
        # never both derive their previous_hash from the same last row.
        db.session.execute(
            select(Tenant.id)
            .where(Tenant.id == tenant_id)
            .with_for_update()
        ).scalar_one()

        repo = AuditRepository(tenant_id=tenant_id)
        last = repo.latest()
        previous_hash = last.hash_chain if last else GENESIS_HASH

        timestamp = datetime.now(timezone.utc)
        timestamp_iso = timestamp.isoformat()
        metadata = metadata or {}

        digest = compute_hash(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            title=title,
            metadata=metadata,
            timestamp_iso=timestamp_iso,
            previous_hash=previous_hash,
        )

        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            title=title,
            metadata_json=metadata,
            previous_hash=previous_hash,
            hash_chain=digest,
            created_at=timestamp,
            timestamp_iso=timestamp_iso,
        )
        db.session.add(log)
        db.session.flush()
        # NO COMMIT HERE - Handled by route/service transaction.
        return log

    @staticmethod
    def verify_chain(tenant_id: int):
        """
        Walk this tenant's audit log in creation order and recompute every
        hash, confirming both the stored digest and the previous-link.
        """
        repo = AuditRepository(tenant_id=tenant_id)
        logs = repo.all_ordered()

        expected_previous = GENESIS_HASH
        for log in logs:
            digest = compute_hash(
                tenant_id=log.tenant_id,
                user_id=log.user_id,
                action=log.action,
                title=log.title,
                metadata=log.metadata_json,
                timestamp_iso=log.timestamp_iso,
                previous_hash=log.previous_hash,
            )
            if log.previous_hash != expected_previous or digest != log.hash_chain:
                return False, log.id
            expected_previous = log.hash_chain

        return True, None
