# API Routers
# All API endpoint modules

from app.routers import (
    auth, crm, hr, inventory, finance, projects,
    ai, documents, reports, workflows, payments,
    integrations, analytics, admin, websocket,
    search, permissions, llm
)

__all__ = [
    'auth', 'crm', 'hr', 'inventory', 'finance', 'projects',
    'ai', 'documents', 'reports', 'workflows', 'payments',
    'integrations', 'analytics', 'admin', 'websocket',
    'search', 'permissions', 'llm'
]
