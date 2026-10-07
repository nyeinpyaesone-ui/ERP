from collections.abc import Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.config import settings as default_settings
from app.routers import (
    admin,
    ai,
    analytics,
    auth,
    crm,
    documents,
    finance,
    health,
    health_root,
    hr,
    integrations,
    inventory,
    llm,
    payments,
    permissions,
    projects,
    reports,
    search,
    websocket,
    workflows,
)

# (module, prefix, tags) — single table so the factory and the module-level
# app below cannot drift apart.
ROUTER_MOUNTS: tuple[tuple[object, str, list[str]], ...] = (
    (auth.router, "/api/v1/auth", ["Authentication"]),
    (crm.router, "/api/v1/crm", ["CRM"]),
    (hr.router, "/api/v1/hr", ["HR"]),
    (inventory.router, "/api/v1/inventory", ["Inventory"]),
    (finance.router, "/api/v1/finance", ["Finance"]),
    (projects.router, "/api/v1/projects", ["Projects"]),
    (ai.router, "/api/v1/ai", ["AI"]),
    (documents.router, "/api/v1/documents", ["Documents"]),
    (reports.router, "/api/v1/reports", ["Reports"]),
    (workflows.router, "/api/v1/workflows", ["Workflows"]),
    (payments.router, "/api/v1/payments", ["Payments"]),
    (integrations.router, "/api/v1/integrations", ["Integrations"]),
    (analytics.router, "/api/v1/analytics", ["Analytics"]),
    (admin.router, "/api/v1/admin", ["Admin"]),
    (websocket.router, "/api/v1/ws", ["WebSocket"]),
    (search.router, "/api/v1/search", ["Search"]),
    (permissions.router, "/api/v1/permissions", ["Permissions"]),
    (llm.router, "/api/v1/llm", ["LLM"]),
    (health.router, "/api/v1", ["Health"]),
    (health_root.router, "", ["Health"]),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Yield control for the application lifetime; dispose pools on shutdown."""
    yield
    from app.database import engine

    engine.dispose()


def create_app(
    settings_override: Settings | dict | None = None,
    mounts: Iterable[tuple[object, str, list[str]]] | None = None,
) -> FastAPI:
    """Application factory (Twelve-Factor friendly).

    - settings_override: a Settings instance or dict of field overrides,
      e.g. create_app({"ENVIRONMENT": "test"}). Lets tests boot a fully
      isolated app without monkeypatching the module-level singleton.
    - mounts: replace the router table (narrow boots for focused tests).
    """
    if isinstance(settings_override, Settings):
        cfg = settings_override
    elif settings_override:
        cfg = Settings(**settings_override)
    else:
        cfg = default_settings

    app = FastAPI(
        title=cfg.APP_NAME,
        description="Enterprise Resource Planning with AI-powered features",
        version=cfg.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    for router, prefix, tags in mounts if mounts is not None else ROUTER_MOUNTS:
        app.include_router(router, prefix=prefix, tags=tags)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    async def root():
        return {
            "name": cfg.APP_NAME,
            "version": cfg.APP_VERSION,
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
                "Alembic Migrations",
            ],
        }

    return app


# Uvicorn entrypoint (app.main:app) and tests keep a concrete instance;
# create_app() is the sanctioned way to boot variants.
app = create_app(settings_override=default_settings)
