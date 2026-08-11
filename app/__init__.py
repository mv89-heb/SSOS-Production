import os

from flask import Flask, jsonify
from sqlalchemy import select
from werkzeug.exceptions import HTTPException

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter, swagger, cors


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    # Production must fail closed instead of silently starting with a known
    # Flask secret, a local SQLite fallback, or an implicit localhost CORS
    # policy. Explicit test/development configs remain self-contained.
    if config_class.__name__ == "ProductionConfig":
        missing = [
            name for name in ("SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                "Missing required production environment variable(s): "
                + ", ".join(missing)
            )

    _ensure_directories(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _ensure_directories(app):
    os.makedirs(app.instance_path, exist_ok=True)
    upload_dir = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_dir


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

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

        stmt = (
            select(User)
            .join(User.tenant)
            .where(
                User.id == parsed_id,
                User.active.is_(True),
                Tenant.active.is_(True),
            )
        )
        return db.session.execute(stmt).scalar_one_or_none()


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.orders import orders_bp
    from app.routes.catalog import catalog_bp
    from app.routes.audit import audit_bp
    from app.routes.notifications import notifications_bp
    from app.routes.health import health_bp
    from app.routes.imports import imports_bp
    from app.routes.users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(users_bp)

    csrf.exempt(health_bp)


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_exception(e):
        return jsonify({
            "success": False,
            "error": e.name.lower().replace(" ", "_"),
            "message": e.description,
        }), e.code
