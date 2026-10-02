import asyncio
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Invoice, Payment

router = APIRouter()

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentIntentRequest(BaseModel):
    invoice_id: int
    amount: float | None = None


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

    amount = data.amount or float(invoice.total - (invoice.amount_paid or 0))
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
            "amount": amount,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify a Stripe event and return a success acknowledgment.

    For a successful payment intent with a matching invoice, commit a payment
    using ``amount_received / 100`` and increase the invoice's paid amount.
    Mark fully covered invoices paid. Other events and missing invoices are
    acknowledged without changes; repeated events are not deduplicated.
    Raise HTTP 400 for a missing secret or invalid payload/signature. Payload
    shape, invoice-ID conversion, arithmetic, and database errors propagate.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as err:
        raise HTTPException(status_code=400, detail="Invalid signature") from err

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        invoice_id = intent["metadata"].get("invoice_id")

        if invoice_id:
            invoice = await asyncio.to_thread(
                lambda: db.query(Invoice).filter(Invoice.id == int(invoice_id)).first()
            )
            if invoice:
                amount = intent["amount_received"] / 100
                payment = Payment(
                    invoice_id=invoice.id,
                    amount=amount,
                    payment_method="stripe",
                    payment_date=datetime.now().date(),
                    stripe_payment_intent_id=intent["id"],
                    stripe_charge_id=(
                        intent["charges"]["data"][0]["id"]
                        if intent.get("charges")
                        else None
                    ),
                    status="completed",
                )
                await asyncio.to_thread(db.add, payment)
                invoice.amount_paid = (invoice.amount_paid or 0) + amount
                if invoice.amount_paid >= invoice.total:
                    invoice.status = "paid"
                await asyncio.to_thread(db.commit)

    return {"status": "success"}
