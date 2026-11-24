"""Persist a stable Stripe PaymentIntent attempt identity on invoices.

Revision ID: 011
Revises: 010
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("invoices")
    }
    if "stripe_payment_attempt_key" not in columns:
        op.add_column(
            "invoices", sa.Column("stripe_payment_attempt_key", sa.String(64))
        )
    if "stripe_payment_attempt_intent_id" not in columns:
        op.add_column(
            "invoices", sa.Column("stripe_payment_attempt_intent_id", sa.String(255))
        )


def downgrade() -> None:
    # Keep persisted attempt identities so rollback cannot break Stripe retries.
    pass
