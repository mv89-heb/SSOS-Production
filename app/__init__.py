import logging
import os

from flask import Flask, jsonify
from sqlalchemy import select
from werkzeug.exceptions import HTTPException

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter, swagger, cors

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    if config_class.__name__ == "ProductionConfig":
        required = ("SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS", "SQLALCHEMY_DATABASE_URI")
        missing = [name for name in required if not app.config.get(name)]
        if missing:
            raise RuntimeError("Missing required production configuration: " + ", ".join(missing))
        if not app.config["CORS_ORIGINS"]:
            raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin in production")

    _ensure_directories(app)
    _init_extensions(app)
    _ensure_document_analysis_table(app, config_class)
    _install_import_analysis_patches()
    _register_blueprints(app)
    _register_error_handlers(app)
    return app


def _ensure_document_analysis_table(app, config_class):
    """Create the document-analysis table if production DB migrations missed it.

    Alembic remains the canonical schema manager. This narrowly scoped startup
    guard is intentionally idempotent and only creates the table when it is
    absent, preventing an existing production database from failing uploads
    because a deployment did not execute the corresponding migration.
    """
    if config_class.__name__ != "ProductionConfig":
        return

    from app.models.document_analysis import DocumentAnalysis

    try:
        with app.app_context():
            DocumentAnalysis.__table__.create(bind=db.engine, checkfirst=True)
    except Exception:
        logger.exception("Could not ensure document_analyses table exists")
        raise


def _install_import_analysis_patches():
    """Install small compatibility enrichments before import routes are loaded."""
    from app.services.import_supplier_detection import install_supplier_detection_patch
    from app.services.import_validation_integrity import install_import_validation_integrity_patch
    install_supplier_detection_patch()
    install_import_validation_integrity_patch()


def _ensure_directories(app):
    os.makedirs(app.instance_path, exist_ok=True)
    upload_dir = os.path.join(app.instance_path, app.config["PRIVATE_UPLOAD_SUBDIR"])
    os.makedirs(upload_dir, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_dir


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)
    swagger.init_app(app)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "authentication_required"}), 401

    from app.models.tenant import Tenant
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            parsed_id = int(user_id)
        except (TypeError, ValueError):
            return None
        stmt = select(User).join(User.tenant).where(User.id == parsed_id, User.active.is_(True), Tenant.active.is_(True))
        return db.session.execute(stmt).scalar_one_or_none()


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.orders import orders_bp
    from app.routes.catalog import catalog_bp
    from app.routes.category_routes import category_bp
    from app.routes.audit import audit_bp
    from app.routes.notifications import notifications_bp
    from app.routes.health import health_bp
    from app.routes.imports import imports_bp
    from app.routes.bulk_price_update import bulk_price_update_bp
    from app.routes.users import users_bp
    from app.routes.admin import admin_bp
    from app.routes.price_intelligence import price_intelligence_bp
    from app.routes.document_intelligence import document_intelligence_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(bulk_price_update_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(price_intelligence_bp)
    app.register_blueprint(document_intelligence_bp)
    csrf.exempt(health_bp)


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify({"success": False, "error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code
