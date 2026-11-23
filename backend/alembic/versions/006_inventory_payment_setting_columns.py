"""Add inventory movement quantities and payment creator.

Revision ID: 006
Revises: 005_permissions_reconcile
Create Date: 2026-10-02

- inventory_movements: add previous_quantity / new_quantity (NOT NULL with
  server_default so existing rows backfill to 0).
- payments: add created_by FK -> users.id (nullable, SET NULL on delete).
- settings.is_encrypted: preserved; no data is dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005_permissions_reconcile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in _inspector().get_columns(table)}


def _foreign_keys(table: str) -> set[str]:
    return {
        foreign_key.get("name")
        for foreign_key in _inspector().get_foreign_keys(table)
    }


def upgrade() -> None:
    movement_columns = _columns("inventory_movements")
    if "previous_quantity" not in movement_columns:
        op.add_column(
            "inventory_movements",
            sa.Column(
                "previous_quantity", sa.Integer(), nullable=False, server_default="0"
            ),
        )
    if "new_quantity" not in movement_columns:
        op.add_column(
            "inventory_movements",
            sa.Column("new_quantity", sa.Integer(), nullable=False, server_default="0"),
        )

    payment_columns = _columns("payments")
    if "created_by" not in payment_columns:
        op.add_column("payments", sa.Column("created_by", sa.Integer(), nullable=True))
    if "fk_payments_created_by_users" not in _foreign_keys("payments"):
        op.create_foreign_key(
            "fk_payments_created_by_users",
            "payments",
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if "fk_payments_created_by_users" in _foreign_keys("payments"):
        op.drop_constraint(
            "fk_payments_created_by_users", "payments", type_="foreignkey"
        )
    payment_columns = _columns("payments")
    if "created_by" in payment_columns:
        op.drop_column("payments", "created_by")
    movement_columns = _columns("inventory_movements")
    if "new_quantity" in movement_columns:
        op.drop_column("inventory_movements", "new_quantity")
    if "previous_quantity" in movement_columns:
        op.drop_column("inventory_movements", "previous_quantity")
