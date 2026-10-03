from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.routers import crm, documents, finance, hr, inventory

pytestmark = pytest.mark.unit

LIST_HANDLERS = [
    crm.list_companies,
    crm.list_contacts,
    crm.list_deals,
    documents.list_documents,
    finance.list_invoices,
    hr.list_departments,
    hr.list_employees,
    inventory.list_products,
    inventory.list_movements,
]


@pytest.mark.parametrize("handler", LIST_HANDLERS, ids=lambda handler: handler.__name__)
@pytest.mark.parametrize("requested,expected", [(0, 0), (1, 1), (100, 100), (101, 100)])
def test_list_pagination_caps_limit_and_keeps_offset(
    db: Mock, actor: SimpleNamespace, handler, requested: int, expected: int
) -> None:
    assert handler(skip=7, limit=requested, db=db, current_user=actor) == []
    db.query.return_value.offset.assert_called_once_with(7)
    db.query.return_value.limit.assert_called_once_with(expected)


def test_employee_list_excludes_personal_and_salary_data(
    db: Mock, actor: SimpleNamespace
) -> None:
    public = {
        "id": 1,
        "employee_code": "E1",
        "job_title": "Analyst",
        "department_id": 3,
        "hire_date": date(2026, 1, 1),
        "status": "active",
        "employment_type": "full_time",
    }
    employee = SimpleNamespace(
        **public,
        salary=Decimal("1200.00"),
        address="Private address",
        phone="555-0100",
        emergency_contact="Private contact",
        date_of_birth=date(1990, 1, 1),
    )
    db.query.return_value.all.return_value = [employee]
    assert hr.list_employees(db=db, current_user=actor) == [public]


def test_pipeline_limits_each_stage_and_returns_only_summary_fields(
    db: Mock, actor: SimpleNamespace
) -> None:
    deal = SimpleNamespace(
        id=1, title="Deal", value=Decimal("0.10"), stage="prospect", notes="Private"
    )
    no_value = SimpleNamespace(id=2, title="New", value=None, stage="prospect")
    db.query.return_value.all.side_effect = [[deal, no_value], [], [], [], [], []]
    result = crm.get_pipeline(limit_per_stage=2, db=db, current_user=actor)
    assert result["prospect"] == {
        "count": 2,
        "total_value": 0.1,
        "deals": [
            {"id": 1, "title": "Deal", "value": 0.1, "stage": "prospect"},
            {"id": 2, "title": "New", "value": 0.0, "stage": "prospect"},
        ],
    }
    assert result["closed_won"] == {"count": 0, "total_value": 0, "deals": []}
    assert len(result) == 6
    assert [call.args for call in db.query.return_value.limit.call_args_list] == [
        (2,)
    ] * 6
