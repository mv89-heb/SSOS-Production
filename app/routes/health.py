from flask import Blueprint, jsonify
from sqlalchemy import text
from app.extensions import db

health_bp = Blueprint("health", __name__)

@health_bp.route("/", methods=["GET"])
def root():
    """
    App Root
    ---
    tags:
      - Infrastructure
    responses:
      200:
        description: Basic app info
    """
    return jsonify({"application": "SSOS", "status": "running", "version": "1.0"}), 200

@health_bp.route("/health", methods=["GET"])
def health():
    """
    Liveness probe — this is the exact path render.yaml's healthCheckPath
    points at. It intentionally does NOT touch the database (unlike
    /health/ready below): a slow/cold DB connection must never fail the
    platform's liveness check and block a deploy from going live.
    ---
    tags:
      - Infrastructure
    responses:
      200:
        description: The process is up and serving requests
    """
    return jsonify({"status": "ok"}), 200

@health_bp.route("/health/ready", methods=["GET"])
def health_ready():
    """
    Readiness Probe
    ---
    tags:
      - Infrastructure
    responses:
      200:
        description: Database connection check
    """
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready", "database": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 503
