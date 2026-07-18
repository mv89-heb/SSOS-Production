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
        # Flush (NOT commit — commits belong to routes) so the row is persisted
        # within the transaction. This matters twice over:
        #   1. repo.latest() in a subsequent log_event inside the same request
        #      sees this entry, keeping the hash chain unbroken.
        #   2. The instance becomes persistent, so the ORM immutability
        #      listeners (before_update/before_delete) actually fire if anyone
        #      later tries to mutate or delete it. A pending instance would
        #      silently bypass them.
        db.session.flush()
        return log

    @staticmethod
    def verify_chain(tenant_id: int):
        """
        Walks the tenant's audit log in insertion order and verifies both
        invariants of the hash chain:
          1. Linkage  — each entry's previous_hash equals the prior entry's
             hash_chain (the first entry must link to GENESIS_HASH).
          2. Integrity — recomputing the SHA-256 over the stored fields
             reproduces the stored hash_chain, so any tampering with
             action/title/metadata/timestamp (even via raw SQL that bypasses
             the ORM listeners) is detected.

        Returns (is_valid, first_broken_log_id) — (True, None) when intact.
        """
        repo = AuditRepository(tenant_id=tenant_id)
        logs = repo.all_ordered()

        expected_previous = GENESIS_HASH
        for log in logs:
            if log.previous_hash != expected_previous:
                return False, log.id

            recomputed = compute_hash(
                tenant_id=log.tenant_id,
                user_id=log.user_id,
                action=log.action,
                title=log.title,
                metadata=log.metadata_json or {},
                timestamp_iso=log.timestamp_iso,
                previous_hash=log.previous_hash,
            )
            if recomputed != log.hash_chain:
                return False, log.id

            expected_previous = log.hash_chain

        return True, None
