"""Ensure tenancy tables exist without overwriting existing ERP data.

Revision ID: 005_tenancy
Revises: 005

This migration is deliberately additive and idempotent because historical
installations may have recorded the old duplicate revision ID 005 after
applying either the tenancy or permission migration. Existing tables, rows,
columns, indexes, and constraints are preserved.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_tenancy"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {index["name"] for index in _inspector().get_indexes(table)}


def _foreign_keys(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {
        foreign_key.get("name") for foreign_key in _inspector().get_foreign_keys(table)
    }


def _create_index_if_missing(
    name: str, table: str, columns: list[str], unique: bool = False
) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    if "tenants" not in _tables():
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("subdomain", sa.String(100), nullable=False),
            sa.Column("schema_name", sa.String(100), nullable=False),
            sa.Column("plan", sa.String(50), server_default="starter", nullable=False),
            sa.Column("max_users", sa.Integer(), server_default="5", nullable=False),
            sa.Column(
                "max_storage_gb", sa.Integer(), server_default="10", nullable=False
            ),
            sa.Column("subscription_start", sa.Date(), nullable=False),
            sa.Column("subscription_end", sa.Date(), nullable=False),
            sa.Column("timezone", sa.String(50), server_default="UTC", nullable=False),
            sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
            sa.Column("locale", sa.String(10), server_default="en_US", nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )
    _create_index_if_missing(
        "ix_tenants_subdomain", "tenants", ["subdomain"], unique=True
    )
    _create_index_if_missing(
        "ix_tenants_schema_name", "tenants", ["schema_name"], unique=True
    )

    if "tenant_id" not in _columns("users"):
        op.add_column("users", sa.Column("tenant_id", sa.Integer(), nullable=True))
    if "fk_users_tenant" not in _foreign_keys("users"):
        op.create_foreign_key(
            "fk_users_tenant", "users", "tenants", ["tenant_id"], ["id"]
        )
    _create_index_if_missing("ix_users_tenant_id", "users", ["tenant_id"])

    if "vendors" not in _tables():
        op.create_table(
            "vendors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("contact_email", sa.String(255)),
            sa.Column("contact_phone", sa.String(50)),
            sa.Column("address", sa.Text()),
            sa.Column("tax_id", sa.String(100)),
            sa.Column("payment_terms", sa.String(100)),
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column("rating", sa.Integer()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )
    _create_index_if_missing("ix_vendors_tenant_id", "vendors", ["tenant_id"])

    if "purchase_orders" not in _tables():
        op.create_table(
            "purchase_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False
            ),
            sa.Column("po_number", sa.String(50), nullable=False),
            sa.Column(
                "vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False
            ),
            sa.Column(
                "requester_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column(
                "subtotal", sa.Numeric(15, 2), server_default="0", nullable=False
            ),
            sa.Column(
                "tax_amount", sa.Numeric(15, 2), server_default="0", nullable=False
            ),
            sa.Column(
                "total_amount", sa.Numeric(15, 2), server_default="0", nullable=False
            ),
            sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
            sa.Column("status", sa.String(50), server_default="draft", nullable=False),
            sa.Column(
                "approval_level", sa.Integer(), server_default="0", nullable=False
            ),
            sa.Column("approved_at", sa.DateTime(timezone=True)),
            sa.Column("ordered_at", sa.DateTime(timezone=True)),
            sa.Column("received_at", sa.DateTime(timezone=True)),
            sa.Column("expected_delivery_date", sa.Date()),
            sa.Column("actual_delivery_date", sa.Date()),
            sa.Column("shipping_address", sa.Text()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )
    _create_index_if_missing(
        "ix_purchase_orders_po_number", "purchase_orders", ["po_number"], unique=True
    )
    _create_index_if_missing("ix_purchase_orders_status", "purchase_orders", ["status"])
    _create_index_if_missing(
        "ix_purchase_orders_vendor_id", "purchase_orders", ["vendor_id"]
    )
    _create_index_if_missing(
        "ix_purchase_orders_tenant_id", "purchase_orders", ["tenant_id"]
    )

    if "purchase_order_items" not in _tables():
        op.create_table(
            "purchase_order_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "po_id",
                sa.Integer(),
                sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
            sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
            sa.Column("total_price", sa.Numeric(15, 2), nullable=False),
            sa.Column(
                "received_quantity",
                sa.Numeric(10, 2),
                server_default="0",
                nullable=False,
            ),
        )

    if "po_approvals" not in _tables():
        op.create_table(
            "po_approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "po_id",
                sa.Integer(),
                sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "approver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column(
                "status", sa.String(50), server_default="pending", nullable=False
            ),
            sa.Column("comments", sa.Text()),
            sa.Column("approved_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )

    if "transaction_logs" not in _tables():
        op.create_table(
            "transaction_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transaction_id", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("old_values", sa.JSON()),
            sa.Column("new_values", sa.JSON()),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id")),
            sa.Column(
                "status", sa.String(50), server_default="completed", nullable=False
            ),
            sa.Column("error_message", sa.Text()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )
    _create_index_if_missing(
        "ix_transaction_logs_transaction_id",
        "transaction_logs",
        ["transaction_id"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_transaction_logs_entity", "transaction_logs", ["entity_type", "entity_id"]
    )
    _create_index_if_missing(
        "ix_transaction_logs_tenant_id", "transaction_logs", ["tenant_id"]
    )


def downgrade() -> None:
    # Deliberately preserve tenant records and related ERP data.
    pass
