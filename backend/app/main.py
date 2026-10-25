from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.database import engine, Base
from app.routers import (
    auth, crm, hr, inventory, finance, projects,
    ai, documents, reports, workflows, payments,
    integrations, analytics, admin, websocket,
    search, llm, permissions
)
from app.config import settings

# Ensure static directories exist
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(os.path.join(STATIC_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "documents"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "avatars"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "reports"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "temp"), exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Resource Planning with AI-powered features",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    # NOTE: "*" wildcard cannot be combined with allow_credentials=True.
    # Explicit dev origins + configurable FRONTEND_URL only.
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(crm.router, prefix="/api/v1/crm", tags=["CRM"])
app.include_router(hr.router, prefix="/api/v1/hr", tags=["HR"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(finance.router, prefix="/api/v1/finance", tags=["Finance"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])
# Routers that self-declare their /api/v1/* prefix internally (no extra prefix here)
app.include_router(search.router, tags=["Advanced Search"])
app.include_router(llm.router, tags=["LLM Integration"])
app.include_router(permissions.router, tags=["Permissions & RBAC"])

# Mount static file endpoints with specific paths
# NOTE: html=True is only for the root mount (directory listings / index.html).
# Sub-mounts serve raw files and must NOT enable HTML mode.
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")
app.mount("/static/uploads", StaticFiles(directory=os.path.join(STATIC_DIR, "uploads")), name="static_uploads")
app.mount("/static/documents", StaticFiles(directory=os.path.join(STATIC_DIR, "documents")), name="static_documents")
app.mount("/static/images", StaticFiles(directory=os.path.join(STATIC_DIR, "images")), name="static_images")
app.mount("/static/avatars", StaticFiles(directory=os.path.join(STATIC_DIR, "avatars")), name="static_avatars")
app.mount("/static/reports", StaticFiles(directory=os.path.join(STATIC_DIR, "reports")), name="static_reports")

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "features": [
            "Core ERP (CRM, HR, Inventory, Finance, Projects)",
            "AI Chat & RAG",
            "Document Management",
            "Reports & Analytics",
            "Workflow Automation",
            "Stripe Payments",
            "WebSocket Real-time",
            "PWA with Offline Support",
            "AI Forecasting",
            "Bulk Import/Export",
            "Alembic Migrations"
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/live")
async def liveness():
    """K8s liveness probe target (no dependency checks)."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """K8s readiness probe target: verifies DB and Redis connectivity."""
    import sqlalchemy as sa
    import redis as redis_sync

    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # pragma: no cover - runtime dependent
        checks["database"] = f"error: {type(e).__name__}"

    try:
        r = redis_sync.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:  # pragma: no cover - runtime dependent
        checks["redis"] = f"error: {type(e).__name__}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ready" if healthy else "degraded", **checks}

