from datetime import datetime
from sqlalchemy import Column, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_mixin

from app.database import Base

# Dialect-adaptive JSON type: uses JSONB on PostgreSQL, falls back to standard JSON on SQLite
JSONField = JSONB().with_variant(JSON, "sqlite")


@declarative_mixin
class TimestampMixin:
    """Provides created_at and updated_at tracking for all tables."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

