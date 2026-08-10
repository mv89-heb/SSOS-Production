import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Mapper
from sqlalchemy.engine import Connection

from app.extensions import db

GENESIS_HASH = "0" * 64


def compute_hash(tenant_id, user_id, action, title, metadata, timestamp_iso, previous_hash):
    """
    Deterministic SHA-256 hash for one audit log entry, chained to the previous
    entry's hash. metadata is serialized with sort_keys=True so the hash is
    stable regardless of dict insertion order.
    """
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "title": title,
        "metadata": metadata or {},
        "timestamp": timestamp_iso,
        "previous_hash": previous_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    action = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(255))
    metadata_json = db.Column(db.JSON, default=dict)

    previous_hash = db.Column(db.String(64), nullable=False)
    hash_chain = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # The exact ISO-8601 string that was fed into the hash. Kept separate from
    # created_at because datetime columns can lose timezone precision on
    # round-trip through some drivers, which would otherwise make an untampered
    # record fail verification.
    timestamp_iso = db.Column(db.String(40), nullable=False)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "user_email": self.user.email if self.user else None,
            "user_full_name": self.user.full_name if self.user else None,
            "action": self.action,
            "title": self.title,
            "metadata": self.metadata_json,
            "previous_hash": self.previous_hash,
            "hash_chain": self.hash_chain,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "timestamp_iso": self.timestamp_iso,
        }

    def __repr__(self):
        return f"<AuditLog {self.action} tenant={self.tenant_id}>"


# --- Enterprise immutability -------------------------------------------------
# Audit records must never be mutated or removed once written. These listeners
# enforce that invariant at the ORM layer, independent of the service layer.

@event.listens_for(AuditLog, "before_update")
def block_audit_update(mapper: Mapper, connection: Connection, target: AuditLog):
    raise RuntimeError("Audit logs are immutable and cannot be updated.")


@event.listens_for(AuditLog, "before_delete")
def block_audit_delete(mapper: Mapper, connection: Connection, target: AuditLog):
    raise RuntimeError("Audit logs are immutable and cannot be deleted.")
