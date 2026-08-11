import os

import pytest

from app.config import DevelopmentConfig, ProductionConfig, TestingConfig


def test_production_config_import_does_not_require_environment(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    # Importing the class and reading its static attributes must not execute
    # production-only secret validation. Validation belongs to init_app().
    assert ProductionConfig.DEBUG is False
    assert TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"


def test_production_init_app_fails_closed_without_required_environment(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    class DummyApp:
        config = {}

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.init_app(DummyApp())


def test_production_init_app_requires_postgres(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///not-allowed.db")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")

    class DummyApp:
        config = {}

    with pytest.raises(RuntimeError, match="PostgreSQL/Neon"):
        ProductionConfig.init_app(DummyApp())


def test_production_init_app_populates_runtime_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com, https://admin.example.com")

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
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "None"


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
