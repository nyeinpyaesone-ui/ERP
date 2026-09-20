from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
import redis

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health")
async def health_check():
    """Liveness probe: the process is running."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe: PostgreSQL and Redis are available."""
    checks = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        db.rollback()
        checks["database"] = f"failed: {type(exc).__name__}"

    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        client.close()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"failed: {type(exc).__name__}"

    if any(value != "ok" for value in checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )

    return {"status": "ready", "checks": checks}
