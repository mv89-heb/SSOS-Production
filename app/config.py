import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _normalize_db_url(url: str) -> str:
    """Normalize provider-style PostgreSQL URLs for SQLAlchemy."""
    url = (url or "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    # Uploads are private application data. The app factory resolves this to
    # instance/uploads, never app/static/uploads, so Flask's static handler
    # cannot expose uploaded documents directly.
    PRIVATE_UPLOAD_SUBDIR = "uploads"
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

    # Optional AI integration. The application remains fully functional when
    # Gemini is disabled or its API key is absent.
    AI_ENABLED = _env_bool("AI_ENABLED", False)
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").strip().lower()
    GEMINI_ENABLED = _env_bool("GEMINI_ENABLED", False)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "30"))

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(BaseConfig):
    DEBUG = False

    @staticmethod
    def init_app(app):
        """Load and validate production-only secrets at app creation time."""
        secret_key = _required_env("SECRET_KEY")
        database_url = _normalize_db_url(_required_env("DATABASE_URL"))
        cors_origins = _csv_env("CORS_ORIGINS")
        gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        if not cors_origins:
            raise RuntimeError(
                "CORS_ORIGINS must contain at least one allowed origin in production"
            )
        if not database_url.startswith("postgresql"):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL/Neon")

        app.config["SECRET_KEY"] = secret_key
        app.config["DATABASE_URL"] = database_url
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.config["CORS_ORIGINS"] = cors_origins
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"sslmode": "require"},
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "None"

        # Re-read AI settings when the Flask app is created. This makes the
        # running Render environment the source of truth instead of relying
        # only on BaseConfig class attributes. If a Gemini key exists but the
        # optional enable flags were omitted, Gemini is enabled automatically.
        app.config["GEMINI_API_KEY"] = gemini_api_key
        app.config["AI_PROVIDER"] = os.environ.get("AI_PROVIDER", "gemini").strip().lower()
        app.config["AI_ENABLED"] = _env_bool("AI_ENABLED", bool(gemini_api_key))
        app.config["GEMINI_ENABLED"] = _env_bool("GEMINI_ENABLED", bool(gemini_api_key))
        app.config["GEMINI_MODEL"] = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        app.config["GEMINI_TIMEOUT"] = float(os.environ.get("GEMINI_TIMEOUT", "30"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True

    @staticmethod
    def init_app(app):
        db_url = os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ssos_dev.db')}",
        )
        db_url = _normalize_db_url(db_url)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        if db_url.startswith("postgresql"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
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
