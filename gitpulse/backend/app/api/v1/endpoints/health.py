import time
from typing import Optional
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, check_db_health
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])
start_time = time.time()


@router.get("/health", response_model=HealthResponse, summary="Comprehensive system health check")
def health_check(db: Session = Depends(get_db)):
    """
    Returns full health status including database connectivity, uptime, environment, and version.
    """
    settings = get_settings()
    target_engine = db.get_bind() if db else None
    db_health = check_db_health(target_engine=target_engine)
    uptime = round(time.time() - start_time, 2)
    overall_status = "healthy" if db_health.get("connected") else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=uptime,
        database=db_health,
    )


@router.get("/health/liveness", summary="Kubernetes / Docker liveness probe")
def liveness_probe():
    """Confirms the process is alive."""
    return {"status": "alive", "timestamp": time.time()}


@router.get("/health/readiness", summary="Kubernetes / Docker readiness probe")
def readiness_probe(response: Response, db: Session = Depends(get_db)):
    """
    Checks downstream dependencies (e.g., PostgreSQL).
    Returns HTTP 200 if ready to serve traffic, 503 if not.
    """
    target_engine = db.get_bind() if db else None
    db_health = check_db_health(target_engine=target_engine)
    if not db_health.get("connected"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False, "reason": "Database connection unreachable", "details": db_health}
    return {"ready": True, "database": db_health}
