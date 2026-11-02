import logging
import time
from pathlib import Path
from typing import Generator, Dict, Any, Optional, Union
from sqlalchemy import create_engine, text, Engine, Connection
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool

from app.config import get_settings

logger = logging.getLogger("gitpulse.database")

Base = declarative_base()


def create_db_engine(db_url: Optional[str] = None) -> Engine:
    """Creates a configured SQLAlchemy engine with dialect-specific pooling and timeouts."""
    settings = get_settings()
    is_custom_url = db_url is not None
    url = db_url or settings.SQLALCHEMY_DATABASE_URI

    engine_kwargs: Dict[str, Any] = {
        "echo": settings.DB_ECHO,
    }

    if not url or url.startswith("sqlite"):
        engine_kwargs.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        })
        return create_engine(url or "sqlite:///:memory:", **engine_kwargs)

    if is_custom_url:
        # Caller explicitly passed a custom URL (e.g. in tests checking connection failures)
        engine_kwargs.update({
            "connect_args": {"connect_timeout": 1},
            "poolclass": QueuePool,
        })
        return create_engine(url, **engine_kwargs)

    # Test if PostgreSQL is reachable before locking into a failing connection
    try:
        probe = create_engine(url, connect_args={"connect_timeout": 1}, pool_pre_ping=False)
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe.dispose()
        # PostgreSQL is active and healthy
        engine_kwargs.update({
            "connect_args": {"connect_timeout": 3},
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "poolclass": QueuePool,
        })
        return create_engine(url, **engine_kwargs)
    except Exception as exc:
        bundled_db = Path(__file__).resolve().parent.parent / "gitpulse_local.db"

        # In serverless environments (e.g. Vercel, AWS Lambda) or when the application directory
        # is read-only, SQLite cannot create lock/journal files in /var/task.
        # We ensure SQLite operates on a writable path (/tmp/gitpulse_local.db).
        import os
        import shutil
        import tempfile

        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        is_readonly = not os.access(str(bundled_db.parent), os.W_OK)

        if is_serverless or is_readonly:
            writable_db = Path(tempfile.gettempdir()) / "gitpulse_local.db"
            if bundled_db.exists() and not writable_db.exists():
                try:
                    shutil.copy2(str(bundled_db), str(writable_db))
                    logger.info(
                        "Restored bundled SQLite warehouse into writable path at %s (%d bytes)",
                        writable_db,
                        writable_db.stat().st_size,
                    )
                except Exception as copy_err:
                    logger.warning("Could not copy bundled DB to writable path: %s", copy_err)
            db_file = writable_db if writable_db.exists() else bundled_db
        else:
            db_file = bundled_db

        fallback_url = f"sqlite:///{db_file}"
        logger.info(
            "PostgreSQL server unreachable at %s (%s). Falling back to local standalone SQLite warehouse at %s.",
            url.split("@")[-1] if "@" in url else url,
            exc,
            db_file,
        )
        engine_kwargs.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        })
        return create_engine(fallback_url, **engine_kwargs)


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Closes the session automatically upon completion.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health(target_engine: Optional[Union[Engine, Connection]] = None) -> Dict[str, Any]:
    """
    Validates database connectivity by executing a lightweight SELECT 1 ping.
    Supports both Engine and active Connection objects.
    Returns latency and status.
    """
    eng = target_engine or engine
    start_time = time.perf_counter()
    try:
        if hasattr(eng, "connect"):
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
        else:
            eng.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        dialect_name = eng.dialect.name if hasattr(eng, "dialect") else "unknown"
        return {
            "status": "healthy",
            "connected": True,
            "latency_ms": latency_ms,
            "dialect": dialect_name,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("Database health check ping failed: %s", exc)
        return {
            "status": "degraded",
            "connected": False,
            "latency_ms": latency_ms,
            "error": str(exc),
            "dialect": eng.dialect.name if hasattr(eng, "dialect") else "unknown",
        }
