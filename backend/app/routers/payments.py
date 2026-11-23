import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Invoice, Payment
from app.models_stripe import StripeWebhookEvent

router = APIRouter()

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentIntentRequest(BaseModel):
    invoice_id: int
    amount: Decimal | None = Field(default=None, gt=0)


def _amount_from_intent(intent: dict[str, Any]) -> Decimal:
    """Validate the settled amount and currency before recording payment.

    Invoice has no currency field today, so this payment integration is USD-only.
    The PaymentIntent must settle exactly the amount it was created for.
    """
    currency = str(intent.get("currency") or "").lower()
    amount_received = intent.get("amount_received")
    amount_expected = intent.get("amount")

    if currency != "usd":
        raise ValueError("Unexpected Stripe payment currency")
    if not isinstance(amount_received, int) or amount_received <= 0:
        raise ValueError("Invalid Stripe amount received")
    if not isinstance(amount_expected, int) or amount_expected <= 0:
        raise ValueError("Invalid Stripe payment amount")
    if amount_received != amount_expected:
        raise ValueError("Settled amount does not match PaymentIntent amount")

    return Decimal(amount_received) / Decimal(100)


def _process_stripe_event(event: Any) -> str:
    """Process an event atomically; a unique event ID prevents duplicate effects."""
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id:
        raise ValueError("Stripe event ID is missing")

    db: Session = SessionLocal()
    try:
        if (
            db.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.event_id == event_id)
            .first()
        ):
            return "duplicate"

        intent = None
        invoice = None
        amount = None
        payment_intent_id = None

        if event_type == "payment_intent.succeeded":
            intent = event.get("data", {}).get("object", {})
            payment_intent_id = str(intent.get("id") or "")
            invoice_id = (intent.get("metadata") or {}).get("invoice_id")
            if not payment_intent_id or not invoice_id:
                raise ValueError("PaymentIntent is missing required identifiers")
            try:
                parsed_invoice_id = int(invoice_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid invoice metadata") from exc

            invoice = (
                db.query(Invoice)
                .filter(Invoice.id == parsed_invoice_id)
                .with_for_update()
                .first()
            )
            if not invoice:
                raise ValueError("Invoice referenced by PaymentIntent was not found")

            existing_payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if existing_payment:
                db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))
                db.commit()
                return "duplicate"

            amount = _amount_from_intent(intent)
            outstanding = Decimal(invoice.total) - Decimal(invoice.amount_paid or 0)
            if amount > outstanding:
                raise ValueError("Stripe payment exceeds invoice outstanding balance")

        db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))

        if event_type == "payment_intent.succeeded":
            charge_data = (intent.get("charges") or {}).get("data") or []
            payment = Payment(
                invoice_id=invoice.id,
                amount=amount,
                payment_method="stripe",
                payment_date=datetime.now(UTC).date(),
                stripe_payment_intent_id=payment_intent_id,
                stripe_charge_id=charge_data[0].get("id") if charge_data else None,
                status="completed",
            )
            db.add(payment)
            invoice.amount_paid = (invoice.amount_paid or Decimal(0)) + amount
            if invoice.amount_paid >= invoice.total:
                invoice.status = "paid"
            else:
                invoice.status = "partial"

        db.commit()
        return "processed"
    except IntegrityError:
        db.rollback()
        if (
            db.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.event_id == event_id)
            .first()
        ):
            return "duplicate"

        # Concurrent distinct events can still reference an already-recorded
        # PaymentIntent. Acknowledge safely after confirming the unique payment.
        intent = event.get("data", {}).get("object", {})
        payment_intent_id = str(intent.get("id") or "")
        if (
            event_type == "payment_intent.succeeded"
            and payment_intent_id
            and db.query(Payment)
            .filter(Payment.stripe_payment_intent_id == payment_intent_id)
            .first()
        ):
            db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))
            db.commit()
            return "duplicate"
        raise
    finally:
        db.close()


@router.post("/create-intent")
def create_payment_intent(
    data: PaymentIntentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Stripe not configured")

    invoice = db.query(Invoice).filter(Invoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    outstanding = Decimal(invoice.total) - Decimal(invoice.amount_paid or 0)
    amount = data.amount if data.amount is not None else outstanding
    if amount != amount.quantize(Decimal("0.01")):
        raise HTTPException(
            status_code=422, detail="Payment amount must use at most two decimal places"
        )
    if amount <= 0 or amount > outstanding:
        raise HTTPException(
            status_code=422,
            detail="Payment amount exceeds the outstanding invoice balance",
        )
    amount_cents = int(amount * 100)
    paid_cents = int(Decimal(invoice.amount_paid or 0) * 100)

    try:
        paid_cents = int(Decimal(invoice.amount_paid or 0) * 100)
        idempotency_key = (
            f"invoice-{invoice.id}-amount-{amount_cents}-paid-{paid_cents}"
        )
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            idempotency_key=idempotency_key,
            metadata={
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
            },
        )
        invoice.stripe_payment_intent_id = intent.id
        db.commit()
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": float(amount),
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        }
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=400, detail="Payment provider request failed"
        ) from exc


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Verify Stripe signature then process in a worker-owned DB session."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError) as err:
        raise HTTPException(status_code=400, detail="Invalid signature") from err

    try:
        result = await asyncio.to_thread(_process_stripe_event, event)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="Invalid Stripe event payload"
        ) from exc

    return {"status": result}
