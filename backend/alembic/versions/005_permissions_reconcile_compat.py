"""Re-apply the frozen permission catalogue after the legacy 005 collision.

Revision ID: 005_permissions_reconcile
Revises: 005_tenancy

This migration is additive and idempotent. It uses a frozen permission list
rather than importing the mutable application catalogue at migration time.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "005_permissions_reconcile"
down_revision: str | None = "005_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCES = (
    "activity_logs",
    "ai",
    "analytics",
    "companies",
    "contacts",
    "deals",
    "departments",
    "documents",
    "employees",
    "integrations",
    "invoices",
    "inventory",
    "jev_intercept",
    "migrations",
    "notifications",
    "payments",
    "products",
    "projects",
    "reports",
    "search",
    "settings",
    "tasks",
    "users",
    "webhooks",
    "workflows",
)
STANDARD_ACTIONS = ("create", "read", "update", "delete", "list")
RESOURCE_EXTRA_ACTIONS = {
    "invoices": ("export", "import"),
    "products": ("export", "import"),
    "contacts": ("export", "import"),
    "reports": ("export",),
    "analytics": ("export",),
    "documents": ("export",),
    "inventory": ("adjust",),
    "payments": ("refund",),
    "webhooks": ("test",),
    "migrations": ("manage",),
    "integrations": ("test",),
}


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("name", sa.String(150)),
        sa.column("resource", sa.String(100)),
        sa.column("action", sa.String(100)),
        sa.column("description", sa.String(255)),
    )
    names = {
        f"{resource}:{action}"
        for resource in RESOURCES
        for action in STANDARD_ACTIONS
    }
    names.update(
        f"{resource}:{action}"
        for resource, actions in RESOURCE_EXTRA_ACTIONS.items()
        for action in actions
    )
    rows = []
    for name in sorted(names):
        resource, action = name.split(":", 1)
        description = f"{action.replace('_', ' ').capitalize()} {resource.replace('_', ' ')}"
        rows.append(
            {
                "name": name,
                "resource": resource,
                "action": action,
                "description": description,
            }
        )
    if rows:
        statement = insert(permissions).values(rows).on_conflict_do_nothing(
            index_elements=["name"]
        )
        op.execute(statement)


def downgrade() -> None:
    # Additive permission catalogue reconciliation is intentionally irreversible.
    pass
