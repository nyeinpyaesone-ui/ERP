"""Persist Stripe event IDs and enforce PaymentIntent uniqueness.

Revision ID: 009
Revises: 008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("""
            SELECT stripe_payment_intent_id
            FROM payments
            WHERE stripe_payment_intent_id IS NOT NULL
            GROUP BY stripe_payment_intent_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """)).first()
    if duplicates:
        raise RuntimeError(
            "Cannot add PaymentIntent uniqueness: duplicate payment intent IDs "
            "already exist in payments. Reconcile these rows before retrying."
        )

    inspector = sa.inspect(bind)
    payment_indexes = {
        index["name"]: index for index in inspector.get_indexes("payments")
    }
    payment_index_name = "uq_payments_stripe_payment_intent_id"
    if payment_index_name in payment_indexes:
        existing = payment_indexes[payment_index_name]
        if existing.get("column_names") != ["stripe_payment_intent_id"] or not existing.get("unique"):
            raise RuntimeError(
                "Existing PaymentIntent index has an unexpected definition."
            )
    else:
        op.create_index(
            payment_index_name,
            "payments",
            ["stripe_payment_intent_id"],
            unique=True,
            postgresql_where=sa.text("stripe_payment_intent_id IS NOT NULL"),
        )

    if not inspector.has_table("stripe_webhook_events"):
        op.create_table(
            "stripe_webhook_events",
            sa.Column("event_id", sa.String(length=255), nullable=False),
            sa.Column("event_type", sa.String(length=255), nullable=False),
            sa.Column(
                "processed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("event_id", name="pk_stripe_webhook_events"),
        )
    else:
        columns = {
            column["name"]
            for column in inspector.get_columns("stripe_webhook_events")
        }
        if not {"event_id", "event_type", "processed_at"}.issubset(columns):
            raise RuntimeError("Existing Stripe webhook event table is incomplete.")

    event_indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("stripe_webhook_events")
    }
    if "ix_stripe_webhook_events_processed_at" not in event_indexes:
        op.create_index(
            "ix_stripe_webhook_events_processed_at",
            "stripe_webhook_events",
            ["processed_at"],
            unique=False,
        )


def downgrade() -> None:
    # Keep payment idempotency records and constraints; downgrade must not erase
    # the event history or weaken duplicate-payment protection.
    pass
