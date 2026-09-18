from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
import redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Liveness probe - process is alive"""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe - dependencies are available"""
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
    
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks
    }