from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models import Product, InventoryMovement
from app.auth import get_current_user
from app.services.permissions import require_permission
from app.services.activity_log import log_activity

router = APIRouter()

class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: Decimal = Decimal("0")
    cost_price: Optional[Decimal] = None
    quantity_in_stock: int = 0
    reorder_level: int = 10
    reorder_quantity: int = 50
    supplier: Optional[str] = None
    supplier_contact: Optional[str] = None
    status: str = "active"
    barcode: Optional[str] = None
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    quantity_in_stock: Optional[int] = None
    reorder_level: Optional[int] = None
    reorder_quantity: Optional[int] = None
    supplier: Optional[str] = None
    supplier_contact: Optional[str] = None
    status: Optional[str] = None
    barcode: Optional[str] = None
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None

class MovementCreate(BaseModel):
    product_id: int
    movement_type: str
    quantity: int
    unit_cost: Optional[Decimal] = None
    reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator("movement_type")
    @classmethod
    def validate_movement_type(cls, v: str) -> str:
        allowed = {"in", "out", "adjustment"}
        if v not in allowed:
            raise ValueError(f"movement_type must be one of: {', '.join(allowed)}")
        return v

ALLOWED_MOVEMENT_TYPES = {"in", "out", "adjustment"}

@router.post("/products")
def create_product(data: ProductCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("products", "create"))):
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    log_activity(db, user_id=current_user.id, action="product_created", entity_type="product", entity_id=product.id)
    return product

@router.get("/products")
def list_products(
    category: Optional[str] = None,
    status: Optional[str] = None,
    low_stock: bool = False,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("products", "read"))
):
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
def get_product(product_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("products", "read"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/products/{product_id}")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), current_user = Depends(require_permission("products", "update"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product

@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("products", "delete"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}

@router.post("/movements")
def create_movement(data: MovementCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("inventory", "create"))):
    # Lock product row to prevent race conditions
    product = db.query(Product).filter(Product.id == data.product_id).with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if data.movement_type == "in":
        product.quantity_in_stock += data.quantity
    elif data.movement_type == "out":
        if product.quantity_in_stock < data.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        product.quantity_in_stock -= data.quantity
    elif data.movement_type == "adjustment":
        product.quantity_in_stock = data.quantity
    else:
        raise HTTPException(status_code=400, detail=f"Invalid movement_type. Allowed: {', '.join(ALLOWED_MOVEMENT_TYPES)}")

    product.updated_at = datetime.utcnow()
    movement = InventoryMovement(
        product_id=data.product_id,
        movement_type=data.movement_type,
        quantity=data.quantity,
        unit_cost=data.unit_cost,
        reference=data.reference,
        notes=data.notes,
        created_by=current_user.id
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    log_activity(db, user_id=current_user.id, action="inventory_moved", entity_type="inventory_movement", entity_id=movement.id)
    return movement

@router.get("/movements")
def list_movements(
    product_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("inventory", "read"))
):
    if limit > 100:
        limit = 100
    query = db.query(InventoryMovement)
    if product_id:
        query = query.filter(InventoryMovement.product_id == product_id)
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)
    return query.order_by(InventoryMovement.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/dashboard")
def inventory_dashboard(db: Session = Depends(get_db), current_user = Depends(require_permission("reports", "read"))):
    total_products = db.query(Product).count()
    total_stock_value = db.query(func.sum(Product.quantity_in_stock * Product.unit_price)).scalar() or Decimal("0")
    low_stock_count = db.query(Product).filter(Product.quantity_in_stock <= Product.reorder_level).count()
    out_of_stock = db.query(Product).filter(Product.quantity_in_stock == 0).count()

    return {
        "total_products": total_products,
        "total_stock_value": float(total_stock_value),
        "low_stock_count": low_stock_count,
        "out_of_stock": out_of_stock,
        "categories": db.query(Product.category, func.count(Product.id)).group_by(Product.category).all()
    }