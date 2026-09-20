from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models import Product, InventoryMovement
from app.auth import get_current_user
from app.services.activity_log import log_activity

router = APIRouter()

VALID_MOVEMENT_TYPES = {"opening", "in", "out", "adjustment", "return"}


class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: float = 0
    cost_price: Optional[float] = None
    reorder_level: int = 10
    reorder_quantity: int = 50
    supplier: Optional[str] = None
    supplier_contact: Optional[str] = None
    status: str = "active"
    barcode: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("sku is required")
        return value.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name is required")
        return value.strip()


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    reorder_level: Optional[int] = None
    reorder_quantity: Optional[int] = None
    supplier: Optional[str] = None
    supplier_contact: Optional[str] = None
    status: Optional[str] = None
    barcode: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[str] = None


class MovementCreate(BaseModel):
    product_id: int
    movement_type: str
    quantity: int
    unit_cost: Optional[float] = None
    reference: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("movement_type")
    @classmethod
    def validate_movement_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in VALID_MOVEMENT_TYPES:
            raise ValueError("invalid movement_type")
        return normalized

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity must be non-zero")
        return value


@router.post("/products")
def create_product(data: ProductCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    product = Product(
        sku=data.sku.strip(),
        name=data.name.strip(),
        description=data.description,
        category=data.category,
        unit_price=Decimal(str(data.unit_price)),
        cost_price=Decimal(str(data.cost_price)) if data.cost_price is not None else None,
        quantity_in_stock=0,
        reorder_level=data.reorder_level,
        reorder_quantity=data.reorder_quantity,
        supplier=data.supplier,
        supplier_contact=data.supplier_contact,
        status=data.status,
        barcode=data.barcode,
        weight=data.weight,
        dimensions=data.dimensions,
    )
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
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    if status:
        query = query.filter(Product.status == status)
    if low_stock:
        query = query.filter(Product.quantity_in_stock <= Product.reorder_level)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    return query.order_by(Product.name.asc()).all()


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/products/{product_id}")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    if "sku" in update_data and update_data["sku"]:
        if db.query(Product).filter(Product.sku == update_data["sku"], Product.id != product_id).first():
            raise HTTPException(status_code=400, detail="SKU already exists")
        product.sku = update_data["sku"].strip()

    if "unit_price" in update_data:
        update_data["unit_price"] = Decimal(str(update_data["unit_price"]))
    if "cost_price" in update_data and update_data["cost_price"] is not None:
        update_data["cost_price"] = Decimal(str(update_data["cost_price"]))

    for key, value in update_data.items():
        if key in {
            "sku", "name", "description", "category", "unit_price", "cost_price",
            "reorder_level", "reorder_quantity", "supplier", "supplier_contact",
            "status", "barcode", "weight", "dimensions"
        }:
            setattr(product, key, value)

    if product.quantity_in_stock is None:
        product.quantity_in_stock = 0

    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    log_activity(db, user_id=current_user.id, action="product_updated", entity_type="product", entity_id=product.id)
    return product


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.post("/movements")
def create_movement(data: MovementCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before_quantity = product.quantity_in_stock
    change_quantity = 0
    after_quantity = before_quantity

    if data.movement_type == "out" and before_quantity < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    if data.movement_type in {"opening", "in", "return"}:
        change_quantity = data.quantity
        after_quantity = before_quantity + data.quantity
        product.quantity_in_stock = after_quantity
    elif data.movement_type == "out":
        change_quantity = -data.quantity
        after_quantity = before_quantity - data.quantity
        product.quantity_in_stock = after_quantity
    elif data.movement_type == "adjustment":
        change_quantity = data.quantity - before_quantity
        after_quantity = data.quantity
        product.quantity_in_stock = data.quantity

    movement = InventoryMovement(
        product_id=data.product_id,
        movement_type=data.movement_type,
        quantity=data.quantity,
        unit_cost=Decimal(str(data.unit_cost)) if data.unit_cost is not None else None,
        reference=data.reference,
        notes=data.notes,
        created_by=current_user.id,
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)

    log_activity(
        db,
        user_id=current_user.id,
        action="inventory_movement_created",
        entity_type="inventory_movement",
        entity_id=movement.id,
        details={
            "product_id": product.id,
            "movement_type": movement.movement_type,
            "before_quantity": before_quantity,
            "change_quantity": change_quantity,
            "after_quantity": after_quantity,
            "reference": data.reference,
        },
    )

    return {
        "id": movement.id,
        "product_id": movement.product_id,
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "before_quantity": before_quantity,
        "change_quantity": change_quantity,
        "after_quantity": after_quantity,
        "reference": movement.reference,
        "notes": movement.notes,
    }


@router.get("/movements")
def list_movements(product_id: Optional[int] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    query = db.query(InventoryMovement)
    if product_id:
        query = query.filter(InventoryMovement.product_id == product_id)
    return query.order_by(InventoryMovement.created_at.desc()).all()


@router.get("/dashboard")
def inventory_dashboard(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    total_products = db.query(Product).count()
    total_stock_value = db.query(func.sum(Product.quantity_in_stock * Product.unit_price)).scalar() or 0
    low_stock_count = db.query(Product).filter(Product.quantity_in_stock <= Product.reorder_level).count()
    out_of_stock = db.query(Product).filter(Product.quantity_in_stock == 0).count()

    return {
        "total_products": total_products,
        "total_stock_value": float(total_stock_value),
        "low_stock_count": low_stock_count,
        "out_of_stock": out_of_stock,
        "categories": db.query(Product.category, func.count(Product.id)).group_by(Product.category).all(),
    }
