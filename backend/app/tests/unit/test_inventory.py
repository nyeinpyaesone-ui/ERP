from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers import inventory

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_movement_rejects_nonpositive_quantity(quantity: int) -> None:
    with pytest.raises(ValidationError, match="Quantity must be positive"):
        inventory.MovementCreate(product_id=1, movement_type="in", quantity=quantity)


@pytest.mark.parametrize("movement_type", ["", "IN", "transfer", "out "])
def test_movement_rejects_unknown_type(movement_type: str) -> None:
    with pytest.raises(ValidationError, match="movement_type must be one of"):
        inventory.MovementCreate(product_id=1, movement_type=movement_type, quantity=1)


@pytest.mark.parametrize(
    "movement_type,quantity,expected",
    [("in", 1, 11), ("out", 3, 7), ("out", 10, 0), ("adjustment", 4, 4)],
)
def test_movement_updates_stock_and_records_actor(
    db: Mock,
    actor: SimpleNamespace,
    audit: Mock,
    movement_type: str,
    quantity: int,
    expected: int,
) -> None:
    product = SimpleNamespace(quantity_in_stock=10, updated_at=None)
    db.query.return_value.first.return_value = product
    data = inventory.MovementCreate(
        product_id=7,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost="0.10",
        reference="delivery-1",
        notes="Counted",
    )

    movement = inventory.create_movement(data, db, actor)

    assert product.quantity_in_stock == expected
    assert product.updated_at is not None
    assert (movement.product_id, movement.movement_type, movement.quantity) == (
        7,
        movement_type,
        quantity,
    )
    assert movement.unit_cost == Decimal("0.10")
    assert (movement.reference, movement.notes, movement.created_by) == (
        "delivery-1",
        "Counted",
        42,
    )
    db.query.return_value.with_for_update.assert_called_once_with()
    db.add.assert_called_once_with(movement)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(movement)


@pytest.mark.parametrize(
    "stock,quantity,status", [(2, 3, 400), (0, 1, 400), (None, 1, 404)]
)
def test_rejected_movement_has_no_writes(
    db: Mock,
    actor: SimpleNamespace,
    stock: int | None,
    quantity: int,
    status: int,
) -> None:
    product = (
        SimpleNamespace(quantity_in_stock=stock, updated_at=None)
        if stock is not None
        else None
    )
    db.query.return_value.first.return_value = product
    data = inventory.MovementCreate(
        product_id=1, movement_type="out", quantity=quantity
    )

    with pytest.raises(HTTPException) as error:
        inventory.create_movement(data, db, actor)

    assert error.value.status_code == status
    if product:
        assert product.quantity_in_stock == stock
        assert product.updated_at is None
    db.add.assert_not_called()
    db.commit.assert_not_called()
