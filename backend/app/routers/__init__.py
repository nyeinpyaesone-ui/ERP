# API Routers
# All API endpoint modules

from . import auth, crm, hr, inventory, finance, projects
from . import ai, documents, reports, workflows, payments
from . import integrations, analytics, admin, websocket, purchase_orders

__all__ = [
    "auth", "crm", "hr", "inventory", "finance", "projects",
    "ai", "documents", "reports", "workflows", "payments",
    "integrations", "analytics", "admin", "websocket", "purchase_orders"
]
