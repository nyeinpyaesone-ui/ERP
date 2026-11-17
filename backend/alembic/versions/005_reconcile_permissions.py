"""Reconcile permissions to catalogue v1

Revision ID: 005
Revises: 004
Create Date: 2024-XX-XX XX:XX:XX.XXXXXX

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ─────────────────────────────────────────────────────────────────────────────
# CATALOGUE DEFINITION (matches app/permissions_catalogue.py)
# ─────────────────────────────────────────────────────────────────────────────

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

SYSTEM_ROLES = ("superadmin", "admin", "manager", "user", "viewer")

# Build the complete expected permission set
ALL_EXPECTED_PERMISSIONS = set()
for resource in (
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
):
    for action in ("create", "read", "update", "delete", "list"):
        ALL_EXPECTED_PERMISSIONS.add(f"{resource}:{action}")

for resource, actions in {
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
}.items():
    for action in actions:
        ALL_EXPECTED_PERMISSIONS.add(f"{resource}:{action}")


def _build_insert_statements() -> list[str]:
    """Generate INSERT statements for all expected permissions with ON CONFLICT DO NOTHING."""
    statements = []
    for perm_name in sorted(ALL_EXPECTED_PERMISSIONS):
        if ":" in perm_name:
            resource, action = perm_name.split(":", 1)
        else:
            parts = perm_name.split(".")
            if len(parts) >= 2:
                resource, action = parts[0], parts[1]
            else:
                continue

        action_label = action.replace("_", " ").capitalize()
        desc = f"{action_label} {resource.replace('_', ' ')}"

        # Escape single quotes
        safe_name = perm_name.replace("'", "''")
        safe_resource = resource.replace("'", "''")
        safe_action = action.replace("'", "''")
        safe_desc = desc.replace("'", "''")

        stmt = (
            f"INSERT INTO permissions (name, resource, action, description) "
            f"VALUES ('{safe_name}', '{safe_resource}', '{safe_action}', '{safe_desc}') "
            f"ON CONFLICT (name) DO NOTHING;"
        )
        statements.append(stmt)
    return statements


def upgrade() -> None:
    """Reconcile permissions table to match the catalogue.

    This migration is ADDITIVE ONLY:
    - Adds missing permissions (resource:action format)
    - Does NOT delete or modify existing permissions
    - Adds missing resources: departments, documents, inventory, payments, tasks, etc.
    """
    statements = _build_insert_statements()
    for stmt in statements:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    """Downgrade is intentionally a no-op for this reconciliation migration.

    This migration is ADDITIVE ONLY. Removing permissions could break existing
    role assignments and is not supported.
    """
    pass
