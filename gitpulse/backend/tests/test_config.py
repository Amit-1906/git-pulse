import os
from app.config import Settings


def test_settings_initialization():
    settings = Settings(
        PROJECT_NAME="GitPulse Test",
        ENVIRONMENT="testing",
        DEBUG=True,
    )
    assert settings.PROJECT_NAME == "GitPulse Test"
    assert settings.ENVIRONMENT == "testing"
    assert settings.is_testing is True
    assert settings.is_production is False
    assert settings.API_V1_STR == "/api/v1"


def test_database_uri_assembly(monkeypatch):
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URI", raising=False)
    settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_SERVER="db.example.com",
        POSTGRES_PORT=5432,
        POSTGRES_DB="test_db",
    )
    assert "postgresql+psycopg2://test_user:test_password@db.example.com:5432/test_db" in settings.SQLALCHEMY_DATABASE_URI
