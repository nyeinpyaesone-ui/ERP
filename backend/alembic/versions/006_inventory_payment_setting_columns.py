"""Add inventory movement quantities, payment creator, drop setting flag

Revision ID: 006
Revises: 005
Create Date: 2026-10-02

- inventory_movements: add previous_quantity / new_quantity (NOT NULL with
  server_default so existing rows backfill to 0).
- payments: add created_by FK -> users.id (nullable, SET NULL on delete).
- settings: drop is_encrypted (removed from the model).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column(
            "previous_quantity", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("new_quantity", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payments",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_created_by_users",
        "payments",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("settings", "is_encrypted")


def downgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "is_encrypted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.drop_constraint("fk_payments_created_by_users", "payments", type_="foreignkey")
    op.drop_column("payments", "created_by")
    op.drop_column("inventory_movements", "new_quantity")
    op.drop_column("inventory_movements", "previous_quantity")
