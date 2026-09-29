from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.routers import crm, hr, inventory

pytestmark = pytest.mark.unit

UPDATE_CASES = [
    (crm.update_company, crm.CompanyUpdate, {"name": "Acme", "phone": "123"}, "phone"),
    (
        crm.update_contact,
        crm.ContactUpdate,
        {"first_name": "Alex", "phone": "123"},
        "phone",
    ),
    (
        hr.update_employee,
        hr.EmployeeUpdate,
        {"employee_code": "E1", "job_title": "Analyst", "phone": "123"},
        "phone",
    ),
    (
        inventory.update_product,
        inventory.ProductUpdate,
        {
            "sku": "P1",
            "name": "Widget",
            "description": "Original",
            "unit_price": Decimal("1.23"),
        },
        "description",
    ),
]


@pytest.mark.parametrize(
    "handler,schema,original,field",
    UPDATE_CASES,
    ids=["company", "contact", "employee", "product"],
)
@pytest.mark.parametrize("value", ["Updated", None])
def test_partial_update_preserves_omitted_fields_and_allows_explicit_null(
    db: Mock,
    actor: SimpleNamespace,
    handler,
    schema,
    original: dict,
    field: str,
    value: str | None,
) -> None:
    record = SimpleNamespace(**original)
    db.query.return_value.first.return_value = record
    result = handler(1, schema(**{field: value}), db, actor)
    assert result is record
    for key, initial in original.items():
        assert getattr(record, key) == (value if key == field else initial)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(record)


@pytest.mark.parametrize(
    "handler,schema,original,field",
    UPDATE_CASES,
    ids=["company", "contact", "employee", "product"],
)
def test_empty_update_preserves_record(
    db: Mock, actor: SimpleNamespace, handler, schema, original: dict, field: str
) -> None:
    record = SimpleNamespace(**original)
    db.query.return_value.first.return_value = record
    handler(1, schema(), db, actor)
    assert all(getattr(record, key) == value for key, value in original.items())


@pytest.mark.parametrize(
    "handler,schema,original,field",
    UPDATE_CASES,
    ids=["company", "contact", "employee", "product"],
)
def test_missing_update_target_does_not_commit(
    db: Mock, actor: SimpleNamespace, handler, schema, original: dict, field: str
) -> None:
    with pytest.raises(HTTPException) as error:
        handler(999, schema(), db, actor)
    assert error.value.status_code == 404
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "schema,payload,field",
    [
        (crm.DealCreate, {"title": "Deal", "value": "9007199254740993.01"}, "value"),
        (hr.DepartmentCreate, {"name": "Engineering", "budget": "0.10"}, "budget"),
        (hr.EmployeeUpdate, {"salary": "1234.56"}, "salary"),
        (inventory.ProductUpdate, {"unit_price": "0.10"}, "unit_price"),
    ],
)
def test_monetary_schemas_preserve_decimal_precision(
    schema, payload: dict, field: str
) -> None:
    assert getattr(schema(**payload), field) == Decimal(payload[field])
