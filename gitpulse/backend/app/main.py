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
import app.models  # Ensure all model declarations are registered on Base

# Initialize logging before FastAPI app creation
setup_logging()
logger = logging.getLogger("gitpulse.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle management.
    """
    logger.info("==================================================")
    logger.info("Starting %s v%s in %s mode", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    db_display = settings.SQLALCHEMY_DATABASE_URI.split("@")[-1] if "@" in settings.SQLALCHEMY_DATABASE_URI else settings.SQLALCHEMY_DATABASE_URI
    logger.info("Database Target: %s", db_display)
    logger.info("==================================================")

    # Initialize tables if the database is reachable
    db_health = check_db_health(engine)
    if db_health.get("connected"):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database schema validated and synchronized successfully.")
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
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.debug = settings.DEBUG

    # Middleware: Request tracing and logging
    app.add_middleware(RequestLoggingMiddleware)

    # Middleware: Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Mount API v1 router
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @app.get("/", include_in_schema=False)
    def root_redirect():
        """Redirects root path directly to interactive API documentation."""
        return RedirectResponse(url="/docs")

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
