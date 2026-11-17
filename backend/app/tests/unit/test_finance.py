from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models import InvoiceItem
from app.routers import finance

pytestmark = pytest.mark.unit


def payment_data(amount: str) -> finance.PaymentCreate:
    return finance.PaymentCreate(
        invoice_id=5,
        amount=amount,
        payment_method="bank",
        payment_date=date(2026, 1, 2),
        notes="Payment reference",
    )


@pytest.mark.parametrize("amount", ["0", "-0.01", "-100", "NaN", "Infinity"])
def test_payment_rejects_invalid_amount(amount: str) -> None:
    with pytest.raises(ValidationError):
        payment_data(amount)


@pytest.mark.parametrize(
    "paid,amount,expected,status",
    [
        (None, "0.10", "0.10", "partial"),
        ("0.10", "0.20", "0.30", "paid"),
        ("0.10", "0.19", "0.29", "partial"),
    ],
)
def test_payment_uses_exact_decimals_and_remaining_balance(
    db: Mock,
    actor: SimpleNamespace,
    audit: Mock,
    paid: str | None,
    amount: str,
    expected: str,
    status: str,
) -> None:
    invoice = SimpleNamespace(
        total=Decimal("0.30"),
        amount_paid=Decimal(paid) if paid else None,
        status="sent",
    )
    db.query.return_value.first.return_value = invoice

    payment = finance.create_payment(payment_data(amount), db, actor)

    assert invoice.amount_paid == Decimal(expected)
    assert invoice.status == status
    assert payment.amount == Decimal(amount)
    assert (payment.invoice_id, payment.created_by, payment.payment_method) == (
        5,
        42,
        "bank",
    )
    assert payment.payment_date == date(2026, 1, 2)
    assert payment.notes == "Payment reference"
    db.query.return_value.with_for_update.assert_called_once_with()
    db.add.assert_called_once_with(payment)
    db.commit.assert_called_once_with()
    audit.assert_called_once()


@pytest.mark.parametrize(
    "total,paid", [("0.30", "0.10"), ("0.30", "0.30"), (None, None)]
)
def test_overpayment_does_not_mutate_invoice(
    db: Mock,
    actor: SimpleNamespace,
    total: str | None,
    paid: str | None,
) -> None:
    invoice = SimpleNamespace(
        total=Decimal(total) if total else None,
        amount_paid=Decimal(paid) if paid else None,
        status="sent",
    )
    db.query.return_value.first.return_value = invoice
    with pytest.raises(
        HTTPException, match="Payment exceeds remaining balance"
    ) as error:
        finance.create_payment(payment_data("0.21"), db, actor)
    assert error.value.status_code == 400
    assert invoice.amount_paid == (Decimal(paid) if paid else None)
    assert invoice.status == "sent"
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_payment_missing_invoice(db: Mock, actor: SimpleNamespace) -> None:
    with pytest.raises(HTTPException) as error:
        finance.create_payment(payment_data("1"), db, actor)
    assert error.value.status_code == 404
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_invoice_calculates_fractional_items_and_tax_exactly(
    db: Mock, actor: SimpleNamespace, audit: Mock
) -> None:
    data = finance.InvoiceCreate(
        invoice_number="INV-1",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        tax_rate="7.5",
        items=[
            finance.InvoiceItemCreate(
                description="First", quantity="3", unit_price="0.10"
            ),
            finance.InvoiceItemCreate(
                description="Second", quantity="1.5", unit_price="0.20"
            ),
        ],
    )
    invoice = finance.create_invoice(data, db, actor)
    assert (invoice.subtotal, invoice.tax_amount, invoice.total) == (
        Decimal("0.60"),
        Decimal("0.045"),
        Decimal("0.645"),
    )
    items = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], InvoiceItem)
    ]
    assert [item.total for item in items] == [Decimal("0.30"), Decimal("0.30")]
    assert invoice.created_by == actor.id
    db.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "status", ["draft", "sent", "paid", "overdue", "cancelled", "partial"]
)
def test_invoice_accepts_allowed_status(
    db: Mock, actor: SimpleNamespace, status: str
) -> None:
    invoice = SimpleNamespace(status="draft")
    db.query.return_value.first.return_value = invoice
    assert finance.update_invoice_status(1, status, db, actor) is invoice
    assert invoice.status == status
    db.commit.assert_called_once_with()


@pytest.mark.parametrize("status", ["", "PAID", "refunded"])
def test_invoice_rejects_invalid_status_before_query(
    db: Mock, actor: SimpleNamespace, status: str
) -> None:
    with pytest.raises(HTTPException) as error:
        finance.update_invoice_status(1, status, db, actor)
    assert error.value.status_code == 400
    db.query.assert_not_called()
    db.commit.assert_not_called()
