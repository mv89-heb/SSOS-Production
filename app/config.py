import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _normalize_db_url(url: str) -> str:
    """Neon/Heroku-style postgres:// URLs must be rewritten for SQLAlchemy 2.x."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured in production")
    return value


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_SIZE", 5 * 1024 * 1024))
    UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".tiff", ".bmp"}
    UPLOAD_MIME_TYPES = {
        "image/png", "image/jpeg", "image/bmp", "image/tiff", "application/pdf",
    }
    IMPORT_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}
    IMPORT_UPLOAD_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "application/csv",
        "text/plain",
    }
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = os.environ.get("WTF_CSRF_ENABLED", "True") == "True"
    RATELIMIT_LOGIN = os.environ.get("RATELIMIT_LOGIN", "10 per minute")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    CORS_ORIGINS = _csv_env(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3100",
    )

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(BaseConfig):
    DEBUG = False

    # Production must fail closed. Never silently fall back to SQLite or a
    # development signing key when a required deployment secret is missing.
    SECRET_KEY = _required_env("SECRET_KEY")
    DATABASE_URL = _required_env("DATABASE_URL")
    CORS_ORIGINS = _csv_env("CORS_ORIGINS")
    if not CORS_ORIGINS:
        raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin in production")

    db_url = _normalize_db_url(DATABASE_URL)
    if not db_url.startswith("postgresql"):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL/Neon")
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"sslmode": "require"},
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ssos_dev.db')}")
    db_url = _normalize_db_url(db_url)
    SQLALCHEMY_DATABASE_URI = db_url
    if db_url.startswith("postgresql"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"sslmode": "require"},
            "pool_pre_ping": True,
        }


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_LOGIN = "10 per minute"


CONFIG_MAP = {
    "production": ProductionConfig,
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    name = name or os.environ.get("FLASK_ENV", "production")
    return CONFIG_MAP.get(name, ProductionConfig)
