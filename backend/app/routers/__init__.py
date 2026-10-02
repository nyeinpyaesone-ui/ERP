# API Routers
# All API endpoint modules

from app.routers import (
    admin,
    ai,
    analytics,
    auth,
    crm,
    documents,
    finance,
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

__all__ = [
    "auth",
    "crm",
    "hr",
    "inventory",
    "finance",
    "projects",
    "ai",
    "documents",
    "reports",
    "workflows",
    "payments",
    "integrations",
    "analytics",
    "admin",
    "websocket",
    "search",
    "permissions",
    "llm",
]
