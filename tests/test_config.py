import pytest

from app.config import DevelopmentConfig, ProductionConfig, TestingConfig


def test_production_config_import_does_not_require_environment(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)
    assert ProductionConfig.DEBUG is False
    assert TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"


def test_production_init_app_fails_closed_without_required_environment(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)

    class DummyApp:
        config = {}

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.init_app(DummyApp())


def test_production_init_app_requires_postgres(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///not-allowed.db")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")

    class DummyApp:
        config = {}

    with pytest.raises(RuntimeError, match="PostgreSQL/Neon"):
        ProductionConfig.init_app(DummyApp())


def test_production_init_app_populates_runtime_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com, https://admin.example.com")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("REMINDER_EXECUTION_WINDOW_MINUTES", "4")

    class DummyApp:
        config = {}

    app = DummyApp()
    ProductionConfig.init_app(app)

    assert app.config["SECRET_KEY"] == "test-secret"
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://")
    assert app.config["CORS_ORIGINS"] == [
        "https://example.com",
        "https://admin.example.com",
    ]
    assert app.config["RATELIMIT_STORAGE_URI"] == "redis://localhost:6379/0"
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "None"
    assert app.config["REMINDER_EXECUTION_WINDOW_MINUTES"] == 4
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_pre_ping"] is True
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_recycle"] == 180
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_size"] == 2
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["max_overflow"] == 0
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_timeout"] == 30


def test_production_init_app_rejects_memory_rate_limit_storage(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")

    class DummyApp:
        config = {}

    with pytest.raises(RuntimeError, match="shared production storage"):
        ProductionConfig.init_app(DummyApp())


def test_testing_config_never_inherits_production_database_uri(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
    assert TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"


def test_development_config_uses_database_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")

    class DummyApp:
        config = {}

    app = DummyApp()
    DevelopmentConfig.init_app(app)
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://")
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_pre_ping"] is True


def test_invalid_reminder_execution_window_fails_fast(monkeypatch):
    monkeypatch.setenv("REMINDER_EXECUTION_WINDOW_MINUTES", "-1")
    with pytest.raises(ValueError, match="REMINDER_EXECUTION_WINDOW_MINUTES"):
        from app.config import _env_int
        _env_int("REMINDER_EXECUTION_WINDOW_MINUTES", 5, minimum=0)


def test_production_entrypoint_runs_migrations_once_before_gunicorn(monkeypatch):
    from scripts import start_production

    events = []

    def fake_run(command, check):
        events.append(("migrate", command, check))

    def fake_execvp(program, args):
        events.append(("exec", program, args))
        raise SystemExit(0)

    monkeypatch.setenv("RUN_MIGRATIONS_ON_START", "true")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setattr(start_production.subprocess, "run", fake_run)
    monkeypatch.setattr(start_production.os, "execvp", fake_execvp)

    with pytest.raises(SystemExit):
        start_production.main()

    assert events[0][0] == "migrate"
    assert events[0][1][1:5] == ["-m", "flask", "--app", "app:create_app()"]
    assert events[0][2] is True
    assert events[1][0] == "exec"
    assert events[1][2][1:3] == ["-w", "1"]
