from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models import Contact, Order, OrderItem, Product, InventoryMovement
from app.auth import get_current_user
from app.services.activity_log import log_activity

router = APIRouter()

VALID_ORDER_STATUSES = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    unit_price: Optional[float] = None


class OrderCreate(BaseModel):
    customer_id: int
    notes: Optional[str] = None
    items: List[OrderItemCreate]

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: List[OrderItemCreate]) -> List[OrderItemCreate]:
        if not value:
            raise ValueError("order must include at least one item")
        return value


class OrderStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in VALID_ORDER_STATUSES:
            raise ValueError("invalid order status")
        return normalized


@router.post("")
def create_order(data: OrderCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    customer = db.query(Contact).filter(Contact.id == data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not data.items:
        raise HTTPException(status_code=400, detail="Order must include at least one item")

    subtotal = Decimal("0")
    order_items: List[OrderItem] = []

    for item in data.items:
        product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.status != "active":
            raise HTTPException(status_code=400, detail=f"Product {product.name} is not active")
        if product.quantity_in_stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product.name}")

        unit_price = Decimal(str(item.unit_price)) if item.unit_price is not None else product.unit_price
        line_total = unit_price * item.quantity
        subtotal += line_total

        order_items.append(
            OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    tax_total = Decimal("0")
    total = subtotal + tax_total

    order = Order(
        customer_id=data.customer_id,
        status="pending",
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        notes=data.notes,
        created_by=current_user.id,
    )

    db.add(order)
    db.flush()

    for item in order_items:
        item.order_id = order.id
        db.add(item)

    for item in data.items:
        product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        before = product.quantity_in_stock
        after = before - item.quantity
        product.quantity_in_stock = after

        db.add(
            InventoryMovement(
                product_id=product.id,
                movement_type="out",
                quantity=item.quantity,
                unit_cost=product.cost_price if product.cost_price is not None else product.unit_price,
                reference=f"order-{order.id}",
                notes=f"Order created for customer {customer.id}",
                before_quantity=before,
                change_quantity=-item.quantity,
                after_quantity=after,
                created_by=current_user.id,
            )
        )

    db.commit()
    db.refresh(order)

    log_activity(
        db,
        user_id=current_user.id,
        action="order_created",
        entity_type="order",
        entity_id=order.id,
        details={"customer_id": data.customer_id, "status": order.status, "total": float(total)},
    )
    return order


@router.get("")
def list_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}/status")
def update_order_status(order_id: int, data: OrderStatusUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = order.status.lower()
    valid_transitions = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"processing", "cancelled"},
        "processing": {"shipped", "cancelled"},
        "shipped": {"delivered"},
        "delivered": set(),
        "cancelled": set(),
    }

    if data.status not in valid_transitions.get(current_status, set()):
        raise HTTPException(status_code=400, detail=f"Invalid status transition from {current_status} to {data.status}")

    order.status = data.status
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    log_activity(
        db,
        user_id=current_user.id,
        action="order_status_updated",
        entity_type="order",
        entity_id=order.id,
        details={"from": current_status, "to": data.status},
    )
    return order


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in {"pending", "cancelled"}:
        raise HTTPException(status_code=400, detail="Only pending or cancelled orders can be deleted")
    db.delete(order)
    db.commit()
    return {"message": "Order deleted"}
