from datetime import datetime, timezone
from app.extensions import db
from app.models.audit import AuditLog, GENESIS_HASH, compute_hash
from app.repositories.audit_repository import AuditRepository

class AuditService:
    @staticmethod
    def log_event(tenant_id: int, user_id, action: str, title: str = "", metadata: dict = None) -> AuditLog:
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
        # NO COMMIT HERE - Handled by route
        return log

    @staticmethod
    def verify_chain(tenant_id: int):
        """
        Walks this tenant's audit log in creation order and recomputes each
        entry's hash from its stored fields, confirming it both matches the
        stored hash_chain value and links to the previous entry's hash.
        Returns (True, None) if the whole chain is intact, or
        (False, <id of first tampered/broken entry>) otherwise.
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
