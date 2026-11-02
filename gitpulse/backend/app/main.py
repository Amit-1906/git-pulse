"""
Vercel ASGI entry point for GitPulse FastAPI backend.

Vercel's @vercel/python runtime imports this module and looks for a variable
named `app` that implements the ASGI callable interface.

This shim ensures the gitpulse/backend directory is on sys.path so that
`from app.xxx import ...` imports resolve correctly regardless of the
working directory Vercel sets during function invocation.
"""
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — ensure `gitpulse/backend` is on sys.path so that
#   `from app.xxx import ...`  resolves correctly.
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()           # gitpulse/backend/app/main.py
_BACKEND_DIR = _THIS_FILE.parent.parent         # gitpulse/backend/
_GITPULSE_DIR = _BACKEND_DIR.parent             # gitpulse/
_PROJECT_ROOT = _GITPULSE_DIR.parent            # repo root

for _p in [str(_BACKEND_DIR), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Environment defaults for Vercel serverless (overridden by Vercel env vars)
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("DEBUG", "false")

# ---------------------------------------------------------------------------
# Import the real application — keep this AFTER path bootstrap
# ---------------------------------------------------------------------------
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.database import engine, Base, check_db_health
import app.models  # noqa: F401 — registers all ORM models on Base

# Initialize structured logging
setup_logging()

logger = logging.getLogger("gitpulse.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("=" * 50)
    logger.info(
        "Starting %s v%s in %s mode",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )
    db_display = (
        settings.SQLALCHEMY_DATABASE_URI.split("@")[-1]
        if "@" in settings.SQLALCHEMY_DATABASE_URI
        else settings.SQLALCHEMY_DATABASE_URI
    )
    logger.info("Database Target: %s", db_display)
    logger.info("=" * 50)

    # Initialize tables if the database is reachable
    db_health = check_db_health(engine)
    if db_health.get("connected"):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database schema validated and synchronized successfully.")
            from app.database import SessionLocal
            from app.services.seed_service import auto_seed_if_empty
            with SessionLocal() as db_session:
                auto_seed_if_empty(db_session)
        except Exception as exc:
            logger.warning("Database schema synchronization warning: %s", exc)
    else:
        logger.warning(
            "Database is unreachable (%s). Running in detached mode without schema sync.",
            db_health.get("error", "offline"),
        )

    yield

    logger.info("Shutting down %s gracefully.", settings.PROJECT_NAME)


def create_application() -> FastAPI:
    """Application factory for GitPulse backend."""
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    _app.state.debug = settings.DEBUG

    # Middleware: Request tracing and logging
    _app.add_middleware(RequestLoggingMiddleware)

    # Middleware: Cross-Origin Resource Sharing (CORS)
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register centralized exception handlers
    register_exception_handlers(_app)

    # Mount API v1 router
    _app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @_app.get("/", include_in_schema=False)
    def root_redirect():
        """Redirects root path directly to interactive API documentation."""
        return RedirectResponse(url="/docs")

    return _app


# ---------------------------------------------------------------------------
# ASGI application object — Vercel discovers this as the serverless handler
# ---------------------------------------------------------------------------
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
