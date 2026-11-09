from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InventoryMovement, Product
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()


class ProductCreate(BaseModel):
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    unit_price: Decimal = Decimal("0")
    cost_price: Decimal | None = None
    quantity_in_stock: int = 0
    reorder_level: int = 10
    reorder_quantity: int = 50
    supplier: str | None = None
    supplier_contact: str | None = None
    status: str = "active"
    barcode: str | None = None
    weight: Decimal | None = None
    dimensions: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    unit_price: Decimal | None = None
    cost_price: Decimal | None = None
    quantity_in_stock: int | None = None
    reorder_level: int | None = None
    reorder_quantity: int | None = None
    supplier: str | None = None
    supplier_contact: str | None = None
    status: str | None = None
    barcode: str | None = None
    weight: Decimal | None = None
    dimensions: str | None = None


class MovementCreate(BaseModel):
    product_id: int
    movement_type: str
    quantity: int
    unit_cost: Decimal | None = None
    reference: str | None = None
    notes: str | None = None

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int, info) -> int:
        """Validate quantity based on movement type.

        For 'in' and 'out': must be positive.
        For 'adjustment': must be non-negative (allows zero).
        """
        movement_type = info.data.get("movement_type")
        if movement_type in ("in", "out"):
            if v <= 0:
                raise ValueError(
                    "Quantity must be positive for 'in' and 'out' movements"
                )
        elif movement_type == "adjustment":
            if v < 0:
                raise ValueError(
                    "Quantity must be non-negative for 'adjustment' movements"
                )
        else:
            if v < 0:
                raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("movement_type")
    @classmethod
    def validate_movement_type(cls, v: str) -> str:
        """Return ``in``, ``out``, or ``adjustment``; raise ValueError otherwise."""
        allowed = {"in", "out", "adjustment"}
        if v not in allowed:
            raise ValueError(f"movement_type must be one of: {', '.join(allowed)}")
        return v


ALLOWED_MOVEMENT_TYPES = {"in", "out", "adjustment"}


@router.post("/products")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("products", "create")),
):
    """Create, commit, and return a product.

    Raise HTTP 400 if the SKU already exists.
    """
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    log_activity(
        db,
        user_id=current_user.id,
        action="product_created",
        entity_type="product",
        entity_id=product.id,
    )
    return product


@router.get("/products")
def list_products(
    category: str | None = None,
    status: str | None = None,
    low_stock: bool = False,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("products", "read")),
):
    """Return a page of products, capping ``limit`` at 100.

    ``skip`` is a record offset. Nonempty category and status filters match
    exactly; search applies a case-insensitive SQL LIKE pattern to names.
    ``low_stock`` includes stock equal to or below the reorder level.
    """
    if limit > 100:
        limit = 100
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    if status:
        query = query.filter(Product.status == status)
    if low_stock:
        query = query.filter(Product.quantity_in_stock <= Product.reorder_level)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    return query.offset(skip).limit(limit).all()


@router.get("/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("products", "read")),
):
    """Return the product, or raise HTTP 404 if it does not exist."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("products", "update")),
):
    """Commit explicitly supplied fields and return the updated product.

    Omitted fields remain unchanged; explicit nulls are applied. Raise
    HTTP 404 if the product does not exist.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    product.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("products", "delete")),
):
    """Delete and commit the product, then return a confirmation message.

    Raise HTTP 404 if the product does not exist.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.post("/movements")
def create_movement(
    data: MovementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("inventory", "create")),
):
    """Commit a stock movement and stock update and return the movement.

    The positive quantity adds stock for ``in``, subtracts stock for ``out``,
    and replaces the stock count for ``adjustment``. Raise HTTP 404 for a
    missing product or HTTP 400 for insufficient stock or an unsupported
    movement type. An outgoing movement may reduce stock to zero.
    An adjustment may set stock to zero.
    """
    # Lock product row to prevent race conditions
    product = (
        db.query(Product)
        .filter(Product.id == data.product_id)
        .with_for_update()
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Capture previous quantity for audit trail
    previous_quantity = product.quantity_in_stock

    if data.movement_type == "in":
        product.quantity_in_stock += data.quantity
    elif data.movement_type == "out":
        if product.quantity_in_stock < data.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        product.quantity_in_stock -= data.quantity
    elif data.movement_type == "adjustment":
        product.quantity_in_stock = data.quantity
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid movement_type. Allowed: {', '.join(ALLOWED_MOVEMENT_TYPES)}",
        )

    product.updated_at = datetime.now(UTC)
    movement = InventoryMovement(
        product_id=data.product_id,
        movement_type=data.movement_type,
        quantity=data.quantity,
        unit_cost=data.unit_cost,
        reference=data.reference,
        notes=data.notes,
        previous_quantity=previous_quantity,
        new_quantity=product.quantity_in_stock,
        created_by=current_user.id,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    log_activity(
        db,
        user_id=current_user.id,
        action="inventory_moved",
        entity_type="inventory_movement",
        entity_id=movement.id,
        details={
            "previous_quantity": previous_quantity,
            "new_quantity": product.quantity_in_stock,
        },
    )
    return movement


@router.get("/movements")
def list_movements(
    product_id: int | None = None,
    movement_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("inventory", "read")),
):
    """Return movements newest first after ``skip`` records, capping ``limit`` at 100.

    Truthy product and movement-type filters are matched exactly.
    """
    if limit > 100:
        limit = 100
    query = db.query(InventoryMovement)
    if product_id:
        query = query.filter(InventoryMovement.product_id == product_id)
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)
    return (
        query.order_by(InventoryMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/dashboard")
def inventory_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports", "read")),
):
    """Return product counts, stock value at unit price, and counts by category.

    Low stock includes quantities equal to the reorder level; out of stock
    counts only quantities equal to zero.
    """
    total_products = db.query(Product).count()
    total_stock_value = db.query(
        func.sum(Product.quantity_in_stock * Product.unit_price)
    ).scalar() or Decimal("0")
    low_stock_count = (
        db.query(Product)
        .filter(Product.quantity_in_stock <= Product.reorder_level)
        .count()
    )
    out_of_stock = db.query(Product).filter(Product.quantity_in_stock == 0).count()

    return {
        "total_products": total_products,
        "total_stock_value": float(total_stock_value),
        "low_stock_count": low_stock_count,
        "out_of_stock": out_of_stock,
        "categories": db.query(Product.category, func.count(Product.id))
        .group_by(Product.category)
        .all(),
    }
