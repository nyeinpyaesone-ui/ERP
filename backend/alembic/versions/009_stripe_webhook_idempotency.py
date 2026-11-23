"""Persist Stripe event IDs for idempotent payment processing.

Revision ID: 009
Revises: 008
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.create_index(
        "ix_stripe_webhook_events_processed_at",
        "stripe_webhook_events",
        ["processed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stripe_webhook_events_processed_at",
        table_name="stripe_webhook_events",
    )
    op.drop_table("stripe_webhook_events")
