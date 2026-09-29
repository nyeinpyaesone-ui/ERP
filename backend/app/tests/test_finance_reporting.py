"""Exercise changed SQL aggregation using only an in-memory invoices table."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Invoice
from app.routers.finance import finance_dashboard

pytestmark = pytest.mark.integration


@pytest.fixture
def invoice_db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Invoice.__table__])
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_monthly_revenue_keeps_the_same_month_in_different_years_separate(
    invoice_db: Session,
) -> None:
    for number, issue_date, total in [
        ("one", date(2024, 1, 1), "10.10"),
        ("two", date(2024, 1, 2), "20.20"),
        ("three", date(2025, 1, 1), "40.40"),
        ("four", date(2025, 2, 1), "50.50"),
    ]:
        invoice_db.add(
            Invoice(
                invoice_number=number,
                issue_date=issue_date,
                due_date=date(2099, 1, 1),
                total=Decimal(total),
            )
        )
    invoice_db.commit()
    result = finance_dashboard(invoice_db, SimpleNamespace(id=42))
    assert sorted(
        result["monthly_revenue"], key=lambda row: (row["year"], row["month"])
    ) == [
        {"year": 2024, "month": 1, "total": 30.3},
        {"year": 2025, "month": 1, "total": 40.4},
        {"year": 2025, "month": 2, "total": 50.5},
    ]


def test_empty_finance_dashboard_has_serializable_zero_totals(
    invoice_db: Session,
) -> None:
    assert finance_dashboard(invoice_db, SimpleNamespace(id=42)) == {
        "total_invoices": 0,
        "total_revenue": 0.0,
        "outstanding": 0.0,
        "overdue_count": 0,
        "monthly_revenue": [],
    }
