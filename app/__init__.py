import logging
import os
import uuid

from flask import Flask, g, jsonify, request
from sqlalchemy import select
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter, swagger, cors

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    if config_class.__name__ == "ProductionConfig":
        required = ("SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS", "SQLALCHEMY_DATABASE_URI", "RATELIMIT_STORAGE_URI")
        missing = [name for name in required if not app.config.get(name)]
        if missing:
            raise RuntimeError("Missing required production configuration: " + ", ".join(missing))
        if not app.config["CORS_ORIGINS"]:
            raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin in production")

    # Render terminates TLS at its edge proxy. Trust exactly one proxy hop so
    # request.is_secure and client IP based controls reflect the original
    # request without blindly trusting arbitrary forwarded headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    _ensure_directories(app)
    _init_extensions(app)
    _install_import_analysis_patches()
    _register_blueprints(app)
    _register_request_context(app)
    _register_security_headers(app)
    _register_error_handlers(app)
    return app


def _install_import_analysis_patches():
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
    if app.config.get("DEBUG"):
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


def _register_request_context(app):
    @app.before_request
    def attach_request_id():
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not request_id or len(request_id) > 128:
            request_id = uuid.uuid4().hex
        g.request_id = request_id

    @app.after_request
    def add_request_id(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", uuid.uuid4().hex)
        return response


def _register_security_headers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not app.debug and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


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
    from app.routes.order_reminders import order_reminders_bp
    from app.routes.google_calendar import google_calendar_bp
    from app.routes.web_push import web_push_bp
    from app.routes.reminder_advanced import reminder_advanced_bp

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
    app.register_blueprint(order_reminders_bp)
    app.register_blueprint(google_calendar_bp)
    app.register_blueprint(web_push_bp)
    app.register_blueprint(reminder_advanced_bp)
    csrf.exempt(health_bp)
    csrf.exempt(web_push_bp)


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify({"success": False, "error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        request_id = getattr(g, "request_id", "unknown")
        logger.exception("Unhandled exception request_id=%s method=%s path=%s", request_id, request.method, request.path)
        return jsonify({
            "success": False,
            "error": "internal_server_error",
            "message": "אירעה שגיאה פנימית בשרת.",
            "request_id": request_id,
        }), 500
