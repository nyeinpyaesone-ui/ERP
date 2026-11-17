import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Liveness probe - process is alive"""
    return {"status": "healthy"}


@router.get("/health/live")
async def health_live():
    """Alias for Kubernetes livenessProbe (path: /health/live)."""
    return {"status": "healthy"}


@router.get("/health/startup")
async def health_startup():
    """Alias for Kubernetes startupProbe (path: /health/startup)."""
    return {"status": "started"}


@router.get("/ready")
@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Return database and Redis check results with ``ready`` or ``not_ready`` status.

    Probe exceptions become failure strings in ``checks``. Either body status
    is returned with HTTP 200; dependency failures are not raised here.
    """
    checks = {}

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"failed: {str(e)}"

    # Redis check
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"failed: {str(e)}"

    # Overall status
    all_ok = all(v == "ok" for v in checks.values())

    return {"status": "ready" if all_ok else "not_ready", "checks": checks}
