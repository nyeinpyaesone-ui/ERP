from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models import PurchaseOrder, PurchaseOrderItem, POApproval, Vendor, User, Product
from app.services.transaction_service import TransactionService
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/v1/purchase-orders", tags=["Purchase Orders"])


# ============== SCHEMAS ==============

class PurchaseOrderItemCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    vendor_id: int
    items: List[PurchaseOrderItemCreate]
    expected_delivery_date: Optional[date] = None
    shipping_address: Optional[str] = None


class PurchaseOrderApprove(BaseModel):
    approved: bool
    comments: Optional[str] = None


# ============== HELPERS ==============

async def generate_po_number(db: AsyncSession) -> str:
    """Generate unique PO number"""
    result = await db.execute(
        select(func.count(PurchaseOrder.id))
    )
    count = result.scalar() or 0
    return f"PO-{date.today().strftime('%Y%m')}-{count + 1:05d}"


async def check_segregation_of_duties(
    db: AsyncSession, 
    requester_id: int, 
    approver_id: Optional[int]
) -> bool:
    """Ensure requester cannot approve their own PO"""
    if approver_id and requester_id == approver_id:
        return False
    return True


def get_approval_level(total_amount: float) -> int:
    """Determine approval level based on amount thresholds"""
    if total_amount < 1000:
        return 1  # Manager approval
    elif total_amount < 10000:
        return 2  # Director approval
    else:
        return 3  # Executive approval


# ============== ENDPOINTS ==============

@router.post("/", response_model=dict)
async def create_purchase_order(
    po_data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(lambda: User(id=1, email="test@example.com"))  # Replace with actual auth
):
    """Create a new purchase order with transactional integrity"""
    
    async with TransactionService.transaction(db):
        # Generate PO number
        po_number = await generate_po_number(db)
        
        # Calculate totals
        subtotal = sum(item.quantity * item.unit_price for item in po_data.items)
        tax_amount = subtotal * 0.1  # 10% tax example
        total_amount = subtotal + tax_amount
        
        # Determine approval level
        approval_level = get_approval_level(total_amount)
        
        # Create PO
        po = PurchaseOrder(
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1,
            po_number=po_number,
            vendor_id=po_data.vendor_id,
            requester_id=current_user.id,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="pending_approval",
            approval_level=approval_level,
            expected_delivery_date=po_data.expected_delivery_date,
            shipping_address=po_data.shipping_address
        )
        
        db.add(po)
        await db.flush()
        
        # Create PO items
        for item_data in po_data.items:
            item = PurchaseOrderItem(
                po_id=po.id,
                product_id=item_data.product_id,
                description=item_data.description,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                total_price=item_data.quantity * item_data.unit_price
            )
            db.add(item)
        
        # Log transaction
        await TransactionService.log_transaction(
            db=db,
            entity_type="purchase_order",
            entity_id=po.id,
            action="create",
            new_values={"po_number": po_number, "total_amount": float(total_amount)},
            user_id=current_user.id,
            tenant_id=po.tenant_id
        )
        
        return {"id": po.id, "po_number": po_number, "status": po.status}


@router.get("/{po_id}")
async def get_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(lambda: User(id=1, email="test@example.com"))
):
    """Get a specific purchase order"""
    
    result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()
    
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # Check tenant isolation
    if hasattr(current_user, 'tenant_id') and po.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": po.id,
        "po_number": po.po_number,
        "vendor_id": po.vendor_id,
        "status": po.status,
        "total_amount": float(po.total_amount),
        "approval_level": po.approval_level,
        "created_at": po.created_at
    }


@router.post("/{po_id}/approve")
async def approve_purchase_order(
    po_id: int,
    approval_data: PurchaseOrderApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(lambda: User(id=1, email="test@example.com"))
):
    """Approve or reject a purchase order"""
    
    async with TransactionService.transaction(db):
        result = await db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == po_id)
        )
        po = result.scalar_one_or_none()
        
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        
        # Check segregation of duties
        if po.requester_id == current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Requester cannot approve their own purchase order"
            )
        
        # Create approval record
        approval = POApproval(
            po_id=po.id,
            approver_id=current_user.id,
            level=po.approval_level,
            status="approved" if approval_data.approved else "rejected",
            comments=approval_data.comments
        )
        db.add(approval)
        
        # Update PO status
        if approval_data.approved:
            if po.approval_level <= 1:
                po.status = "approved"
                po.approved_at = func.now()
            else:
                po.approval_level -= 1
                po.status = "pending_approval"
        else:
            po.status = "rejected"
        
        # Log transaction
        await TransactionService.log_transaction(
            db=db,
            entity_type="purchase_order",
            entity_id=po.id,
            action="approve",
            new_values={"status": po.status, "approved_by": current_user.id},
            user_id=current_user.id,
            tenant_id=po.tenant_id
        )
        
        return {"id": po.id, "status": po.status, "approval_level": po.approval_level}


@router.get("/")
async def list_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(lambda: User(id=1, email="test@example.com", tenant_id=1))
):
    """List purchase orders with tenant isolation"""
    
    tenant_id = getattr(current_user, 'tenant_id', 1)
    
    query = select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id)
    
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    pos = result.scalars().all()
    
    return [
        {
            "id": po.id,
            "po_number": po.po_number,
            "vendor_id": po.vendor_id,
            "status": po.status,
            "total_amount": float(po.total_amount),
            "created_at": po.created_at
        }
        for po in pos
    ]
