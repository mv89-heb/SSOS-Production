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
    MAX_IMPORT_ROWS = int(os.environ.get("MAX_IMPORT_ROWS", 25000))
    MAX_IMPORT_COLUMNS = int(os.environ.get("MAX_IMPORT_COLUMNS", 200))
    UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".tiff", ".bmp"}
    UPLOAD_MIME_TYPES = {"image/png", "image/jpeg", "image/bmp", "image/tiff", "application/pdf"}
    IMPORT_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}
    IMPORT_UPLOAD_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel", "text/csv", "application/csv", "text/plain",
    }
    PRIVATE_UPLOAD_SUBDIR = "uploads"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = os.environ.get("WTF_CSRF_ENABLED", "True") == "True"
    RATELIMIT_LOGIN = os.environ.get("RATELIMIT_LOGIN", "10 per minute")
    RATELIMIT_REGISTER = os.environ.get("RATELIMIT_REGISTER", "5 per hour")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    CORS_ORIGINS = _csv_env("CORS_ORIGINS", "http://localhost:3000,http://localhost:3100")

    AI_ENABLED = _env_bool("AI_ENABLED", False)
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").strip().lower()
    GEMINI_ENABLED = _env_bool("GEMINI_ENABLED", False)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "30"))

    GOOGLE_CALENDAR_CLIENT_ID = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
    GOOGLE_CALENDAR_CLIENT_SECRET = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()
    GOOGLE_CALENDAR_REDIRECT_URI = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI", "").strip()
    GOOGLE_CALENDAR_TIMEZONE = os.environ.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem").strip()
    API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "").strip()
    FRONTEND_PUBLIC_URL = os.environ.get("FRONTEND_PUBLIC_URL", "").strip()

    WEB_PUSH_VAPID_PUBLIC_KEY = os.environ.get("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
    WEB_PUSH_VAPID_PRIVATE_KEY = os.environ.get("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    WEB_PUSH_VAPID_CLAIMS_EMAIL = os.environ.get("WEB_PUSH_VAPID_CLAIMS_EMAIL", "mailto:admin@example.com").strip()

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(BaseConfig):
    DEBUG = False

    @staticmethod
    def init_app(app):
        secret_key = _required_env("SECRET_KEY")
        database_url = _normalize_db_url(_required_env("DATABASE_URL"))
        cors_origins = _csv_env("CORS_ORIGINS")
        gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        ratelimit_storage = _required_env("RATELIMIT_STORAGE_URI")

        if not cors_origins:
            raise RuntimeError("CORS_ORIGINS must contain at least one allowed origin in production")
        if not database_url.startswith("postgresql"):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL/Neon")
        if ratelimit_storage == "memory://":
            raise RuntimeError("RATELIMIT_STORAGE_URI must use shared production storage (for example Redis)")

        app.config["SECRET_KEY"] = secret_key
        app.config["DATABASE_URL"] = database_url
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.config["CORS_ORIGINS"] = cors_origins
        app.config["RATELIMIT_STORAGE_URI"] = ratelimit_storage
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"sslmode": "require"}, "pool_pre_ping": True, "pool_recycle": 300,
        }
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "None"

        app.config["GEMINI_API_KEY"] = gemini_api_key
        app.config["AI_PROVIDER"] = os.environ.get("AI_PROVIDER", "gemini").strip().lower()
        app.config["AI_ENABLED"] = _env_bool("AI_ENABLED", bool(gemini_api_key))
        app.config["GEMINI_ENABLED"] = _env_bool("GEMINI_ENABLED", bool(gemini_api_key))
        app.config["GEMINI_MODEL"] = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
        app.config["GEMINI_TIMEOUT"] = float(os.environ.get("GEMINI_TIMEOUT", "30"))
        app.config["GOOGLE_CALENDAR_CLIENT_ID"] = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()
        app.config["GOOGLE_CALENDAR_CLIENT_SECRET"] = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()
        app.config["GOOGLE_CALENDAR_REDIRECT_URI"] = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI", "").strip()
        app.config["GOOGLE_CALENDAR_TIMEZONE"] = os.environ.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem").strip()
        app.config["API_PUBLIC_URL"] = os.environ.get("API_PUBLIC_URL", "").strip()
        app.config["FRONTEND_PUBLIC_URL"] = os.environ.get("FRONTEND_PUBLIC_URL", "").strip()
        app.config["WEB_PUSH_VAPID_PUBLIC_KEY"] = os.environ.get("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
        app.config["WEB_PUSH_VAPID_PRIVATE_KEY"] = os.environ.get("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
        app.config["WEB_PUSH_VAPID_CLAIMS_EMAIL"] = os.environ.get("WEB_PUSH_VAPID_CLAIMS_EMAIL", "mailto:admin@example.com").strip()


class DevelopmentConfig(BaseConfig):
    DEBUG = True

    @staticmethod
    def init_app(app):
        db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ssos_dev.db')}")
        db_url = _normalize_db_url(db_url)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        if db_url.startswith("postgresql"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"sslmode": "require"}, "pool_pre_ping": True}


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    RATELIMIT_LOGIN = "10 per minute"
    RATELIMIT_REGISTER = "5 per hour"
    RATELIMIT_STORAGE_URI = "memory://"


CONFIG_MAP = {"production": ProductionConfig, "development": DevelopmentConfig, "testing": TestingConfig}


def get_config(name=None):
    name = name or os.environ.get("FLASK_ENV", "production")
    return CONFIG_MAP.get(name, ProductionConfig)
