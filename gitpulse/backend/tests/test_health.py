from fastapi import Response
from app.api.v1.endpoints.health import health_check, liveness_probe, readiness_probe


def test_health_check_endpoint(db_session):
    resp = health_check(db=db_session)
    assert resp.status in ("healthy", "degraded")
    assert resp.version == "0.1.0"
    assert resp.database is not None
    assert resp.uptime_seconds >= 0


def test_liveness_probe_endpoint():
    resp = liveness_probe()
    assert resp["status"] == "alive"
    assert "timestamp" in resp


def test_readiness_probe_endpoint(db_session):
    response = Response()
    resp = readiness_probe(response=response, db=db_session)
    assert "ready" in resp
    assert resp["ready"] is True
