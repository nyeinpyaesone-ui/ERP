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
    amount: float | None = Field(default=None, gt=0)


def _process_stripe_event(event: Any) -> str:
    """Process an event atomically; a unique event ID prevents duplicate effects."""
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id:
        raise ValueError("Stripe event ID is missing")

    db: Session = SessionLocal()
    try:
        if db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).first():
            return "duplicate"

        db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))

        if event_type == "payment_intent.succeeded":
            intent = event["data"]["object"]
            invoice_id = (intent.get("metadata") or {}).get("invoice_id")
            if invoice_id:
                try:
                    parsed_invoice_id = int(invoice_id)
                except (TypeError, ValueError):
                    parsed_invoice_id = None

                if parsed_invoice_id is not None:
                    invoice = (
                        db.query(Invoice)
                        .filter(Invoice.id == parsed_invoice_id)
                        .with_for_update()
                        .first()
                    )
                    if invoice:
                        payment_intent_id = str(intent["id"])
                        existing_payment = (
                            db.query(Payment)
                            .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                            .first()
                        )
                        if not existing_payment:
                            amount = Decimal(int(intent["amount_received"])) / Decimal(100)
                            payment = Payment(
                                invoice_id=invoice.id,
                                amount=amount,
                                payment_method="stripe",
                                payment_date=datetime.now(UTC).date(),
                                stripe_payment_intent_id=payment_intent_id,
                                stripe_charge_id=(
                                    intent["charges"]["data"][0]["id"]
                                    if intent.get("charges", {}).get("data")
                                    else None
                                ),
                                status="completed",
                            )
                            db.add(payment)
                            invoice.amount_paid = (invoice.amount_paid or Decimal(0)) + amount
                            if invoice.amount_paid >= invoice.total:
                                invoice.status = "paid"

        db.commit()
        return "processed"
    except IntegrityError:
        db.rollback()
        if db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).first():
            return "duplicate"

        # A distinct Stripe event can still reference an already-recorded
        # PaymentIntent. Persist this event ID after the payment transaction
        # rolls back so Stripe receives a successful idempotent acknowledgement.
        if event_type == "payment_intent.succeeded":
            intent = event.get("data", {}).get("object", {})
            payment_intent_id = str(intent.get("id") or "")
            if payment_intent_id and db.query(Payment).filter(
                Payment.stripe_payment_intent_id == payment_intent_id
            ).first():
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
    amount = Decimal(str(data.amount)) if data.amount is not None else outstanding
    if amount <= 0 or amount > outstanding:
        raise HTTPException(status_code=422, detail="Payment amount exceeds the outstanding invoice balance")
    amount_cents = int(amount * 100)

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
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
        raise HTTPException(status_code=400, detail="Payment provider request failed") from exc


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
        raise HTTPException(status_code=400, detail="Invalid Stripe event payload") from exc

    return {"status": result}
