from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

from app.database import get_db
from app.models import Invoice, InvoiceItem, Payment
from app.auth import get_current_user
from app.services.permissions import require_permission
from app.services.activity_log import log_activity

router = APIRouter()

class InvoiceItemCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal

class InvoiceCreate(BaseModel):
    invoice_number: str
    contact_id: Optional[int] = None
    company_id: Optional[int] = None
    issue_date: date
    due_date: date
    tax_rate: Decimal = Decimal("0")
    notes: Optional[str] = None
    terms: Optional[str] = None
    items: List[InvoiceItemCreate]

class PaymentCreate(BaseModel):
    invoice_id: int
    amount: Decimal
    payment_method: str
    payment_date: date
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Payment amount must be positive")
        return v

ALLOWED_INVOICE_STATUSES = {"draft", "sent", "paid", "overdue", "cancelled", "partial"}

def generate_invoice_number(db: Session) -> str:
    count = db.query(Invoice).count() + 1
    return f"INV-{datetime.now().year}-{count:05d}"

@router.post("/invoices")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("invoices", "create"))):
    existing = db.query(Invoice).filter(Invoice.invoice_number == data.invoice_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    subtotal = sum(item.quantity * item.unit_price for item in data.items)
    tax_amount = subtotal * (data.tax_rate / Decimal("100"))
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=data.invoice_number,
        contact_id=data.contact_id,
        company_id=data.company_id,
        issue_date=data.issue_date,
        due_date=data.due_date,
        subtotal=subtotal,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        total=total,
        notes=data.notes,
        terms=data.terms,
        created_by=current_user.id
    )
    db.add(invoice)
    db.flush()

    for item_data in data.items:
        item_total = item_data.quantity * item_data.unit_price
        item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=item_data.product_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total=item_total
        )
        db.add(item)

    db.commit()
    db.refresh(invoice)
    log_activity(db, user_id=current_user.id, action="invoice_created", entity_type="invoice", entity_id=invoice.id)
    return invoice

@router.get("/invoices")
def list_invoices(
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoices", "read"))
):
    if limit > 100:
        limit = 100
    query = db.query(Invoice)
    if status:
        query = query.filter(Invoice.status == status)
    if contact_id:
        query = query.filter(Invoice.contact_id == contact_id)
    return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("invoices", "read"))):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.put("/invoices/{invoice_id}/status")
def update_invoice_status(
    invoice_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("invoices", "update"))
):
    if status not in ALLOWED_INVOICE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(ALLOWED_INVOICE_STATUSES)}")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = status
    db.commit()
    db.refresh(invoice)
    return invoice

@router.post("/payments")
def create_payment(data: PaymentCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("invoices", "create"))):
    # Lock the invoice row to prevent race conditions
    invoice = db.query(Invoice).filter(Invoice.id == data.invoice_id).with_for_update().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Validate payment doesn't exceed remaining balance
    remaining = (invoice.total or Decimal("0")) - (invoice.amount_paid or Decimal("0"))
    if data.amount > remaining:
        raise HTTPException(status_code=400, detail=f"Payment exceeds remaining balance of {remaining}")

    payment = Payment(
        invoice_id=data.invoice_id,
        amount=data.amount,
        payment_method=data.payment_method,
        payment_date=data.payment_date,
        notes=data.notes,
        created_by=current_user.id
    )
    db.add(payment)

    invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + data.amount
    if invoice.amount_paid >= invoice.total:
        invoice.status = "paid"
    else:
        invoice.status = "partial"

    db.commit()
    db.refresh(payment)
    log_activity(db, user_id=current_user.id, action="payment_received", entity_type="payment", entity_id=payment.id)
    return payment

@router.get("/dashboard")
def finance_dashboard(db: Session = Depends(get_db), current_user = Depends(require_permission("reports", "read"))):
    total_invoices = db.query(Invoice).count()
    total_revenue = db.query(func.sum(Invoice.amount_paid)).scalar() or Decimal("0")
    outstanding = db.query(func.sum(Invoice.total - Invoice.amount_paid)).filter(Invoice.status != "paid").scalar() or Decimal("0")
    overdue = db.query(Invoice).filter(Invoice.due_date < date.today(), Invoice.status != "paid").count()

    # Monthly revenue with year
    from sqlalchemy import extract
    monthly = db.query(
        extract('year', Invoice.issue_date).label('year'),
        extract('month', Invoice.issue_date).label('month'),
        func.sum(Invoice.total)
    ).group_by(extract('year', Invoice.issue_date), extract('month', Invoice.issue_date)).all()

    return {
        "total_invoices": total_invoices,
        "total_revenue": float(total_revenue),
        "outstanding": float(outstanding),
        "overdue_count": overdue,
        "monthly_revenue": [
            {"year": int(m.year), "month": int(m.month), "total": float(m[2] or 0)}
            for m in monthly
        ]
    }