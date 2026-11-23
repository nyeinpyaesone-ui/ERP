"""Re-apply the current permission catalogue after the legacy 005 collision.

Revision ID: 005_permissions_reconcile
Revises: 005_tenancy

This migration is additive and idempotent. It repairs installations whose
historical revision 005 may have represented either of the colliding files.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

from app.permissions_catalogue import ALL_PERMISSIONS

revision: str = "005_permissions_reconcile"
down_revision: str | None = "005_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("name", sa.String(150)),
        sa.column("resource", sa.String(100)),
        sa.column("action", sa.String(100)),
        sa.column("description", sa.String(255)),
    )
    rows = []
    for name in ALL_PERMISSIONS:
        resource, action = name.split(":", 1)
        rows.append({
            "name": name,
            "resource": resource,
            "action": action,
            "description": f"{action.replace('_', ' ').capitalize()} {resource.replace('_', ' ')}",
        })
    if rows:
        statement = insert(permissions).values(rows).on_conflict_do_nothing(
            index_elements=["name"]
        )
        op.execute(statement)


def downgrade() -> None:
    # Additive permission catalogue reconciliation is intentionally irreversible.
    pass
