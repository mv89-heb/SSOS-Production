import logging

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@health_bp.route("/", methods=["GET"])
def root():
    return jsonify({"application": "SSOS", "status": "running", "version": "1.0"}), 200


@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe: confirms the process is serving HTTP."""
    return jsonify({"status": "ok"}), 200


@health_bp.route("/health/ready", methods=["GET"])
def health_ready():
    """Readiness probe: confirms the database is reachable."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready", "database": "ok"}), 200
    except Exception:
        db.session.rollback()
        logger.exception("Readiness database check failed")
        return jsonify({"status": "error", "database": "unavailable"}), 503
