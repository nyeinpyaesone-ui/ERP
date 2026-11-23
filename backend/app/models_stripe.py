"""Stripe webhook idempotency record.

The event ID is the primary key so concurrent duplicate deliveries cannot
apply invoice/payment side effects more than once.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    event_id = Column(String(255), primary_key=True)
    event_type = Column(String(255), nullable=False)
    processed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
