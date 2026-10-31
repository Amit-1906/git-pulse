from functools import lru_cache
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration using pydantic-settings.
    Supports environment variable overrides and provides defaults.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Information
    PROJECT_NAME: str = "GitPulse"
    PROJECT_DESCRIPTION: str = "End-to-End ELT Platform for GitHub Activity Analytics"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="development | production | testing")
    DEBUG: bool = Field(default=True, description="Debug mode flag")
    API_V1_STR: str = "/api/v1"

    # Server Bind Configuration
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # PostgreSQL Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "gitpulse"
    POSTGRES_PASSWORD: str = "gitpulse_secret"
    POSTGRES_DB: str = "gitpulse_db"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False

    # GitHub REST API Configuration
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_ACCESS_TOKEN: Optional[str] = Field(
        default=None,
        description="Optional personal access token to raise rate limit from 60 to 5000 req/hr",
    )
    GITHUB_API_TIMEOUT: int = 30
    GITHUB_RATE_LIMIT_BUFFER: int = 50

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # 'json' or 'text'

    # Security
    SECRET_KEY: str = "insecure-gitpulse-development-secret-key-change-in-production"

    # dbt Configuration
    DBT_PROJECT_DIR: str = "./dbt"
    DBT_PROFILES_DIR: str = "./dbt"

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        if isinstance(v, str) and v.strip():
            return v
        values = info.data
        user = values.get("POSTGRES_USER", "gitpulse")
        password = values.get("POSTGRES_PASSWORD", "gitpulse_secret")
        server = values.get("POSTGRES_SERVER", "localhost")
        port = values.get("POSTGRES_PORT", 5432)
        db = values.get("POSTGRES_DB", "gitpulse_db")
        return f"postgresql+psycopg2://{user}:{password}@{server}:{port}/{db}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT.lower() == "testing"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton instance."""
    return Settings()

