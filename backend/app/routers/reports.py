from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date
import io
import base64

from app.database import get_db
from app.models import Invoice, Deal, Contact, Product, Employee, Project, Task
from app.auth import get_current_user
from app.services.activity_log import log_activity

router = APIRouter()

@router.get("/revenue")
def revenue_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from sqlalchemy import func, extract, text

    # Build dynamic SQL for date filtering
    where_clause = "WHERE 1=1"
    params = {}
    if start_date:
        where_clause += " AND issue_date >= :start_date"
        params['start_date'] = start_date
    if end_date:
        where_clause += " AND issue_date <= :end_date"
        params['end_date'] = end_date

    # Single aggregated query instead of loading all invoices
    result = db.execute(text(f"""
        SELECT 
            COALESCE(SUM(total), 0) as total_revenue,
            COALESCE(SUM(amount_paid), 0) as total_paid,
            COUNT(*) as invoice_count
        FROM invoices {where_clause}
    """), params).first()
    
    total = float(result.total_revenue or 0)
    paid = float(result.total_paid or 0)
    invoice_count = result.invoice_count or 0

    # Monthly breakdown with single grouped query
    monthly_query = text(f"""
        SELECT 
            EXTRACT(YEAR FROM issue_date) as year,
            EXTRACT(MONTH FROM issue_date) as month,
            COALESCE(SUM(total), 0) as total,
            COUNT(*) as count
        FROM invoices {where_clause}
        GROUP BY year, month
        ORDER BY year, month
    """)
    monthly = db.execute(monthly_query, params).all()

    return {
        "total_revenue": total,
        "total_paid": paid,
        "outstanding": total - paid,
        "invoice_count": invoice_count,
        "monthly_breakdown": [
            {"month": f"{int(m.year)}-{int(m.month):02d}", "revenue": float(m.total), "count": m.count}
            for m in monthly
        ]
    }

@router.get("/pipeline")
def pipeline_report(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Optimized pipeline report using single GROUP BY query instead of 6 separate queries."""
    from sqlalchemy import func, text
    
    # Single aggregated query
    result = db.execute(text("""
        SELECT 
            stage,
            COUNT(*) as count,
            COALESCE(SUM(value), 0) as total_value
        FROM deals
        GROUP BY stage
    """)).all()
    
    # Convert to dict for fast lookup
    stats_dict = {row.stage: {"count": row.count, "value": float(row.total_value)} for row in result}
    
    # Build response with defaults for stages with no deals
    stages = ["prospect", "qualification", "proposal", "negotiation", "closed_won", "closed_lost"]
    return {
        stage: stats_dict.get(stage, {"count": 0, "value": 0.0})
        for stage in stages
    }

@router.get("/inventory")
def inventory_report(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Optimized inventory report using aggregated queries and limited data fetch."""
    from sqlalchemy import func, text
    
    # Get aggregate stats in one query
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_products,
            COALESCE(SUM(quantity_in_stock * unit_price), 0) as total_value,
            COUNT(CASE WHEN quantity_in_stock <= reorder_level THEN 1 END) as low_stock_count
        FROM products
    """)).first()
    
    # Only fetch low stock items (typically small dataset)
    low_stock_items = db.query(Product).filter(Product.quantity_in_stock <= Product.reorder_level).limit(100).all()
    
    # Get category breakdown efficiently
    categories_result = db.execute(text("""
        SELECT category, COUNT(*) as count, COALESCE(SUM(quantity_in_stock), 0) as stock
        FROM products
        WHERE category IS NOT NULL
        GROUP BY category
    """)).all()
    
    return {
        "total_products": stats.total_products or 0,
        "total_stock_value": float(stats.total_value or 0),
        "low_stock_count": stats.low_stock_count or 0,
        "low_stock_items": [
            {"id": p.id, "name": p.name, "sku": p.sku, "stock": p.quantity_in_stock}
            for p in low_stock_items
        ],
        "categories": {
            cat.category: {"count": cat.count, "stock": int(cat.stock)}
            for cat in categories_result
        }
    }

@router.get("/chart/revenue")
def revenue_chart(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from sqlalchemy import func, extract

        monthly = db.query(
            extract('month', Invoice.issue_date).label('month'),
            extract('year', Invoice.issue_date).label('year'),
            func.sum(Invoice.total).label('total')
        ).group_by('year', 'month').order_by('year', 'month').all()

        if not monthly:
            return {"chart": None}

        labels = [f"{m.year}-{m.month:02d}" for m in monthly]
        values = [float(m.total) for m in monthly]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(labels, values, color='#4f46e5')
        ax.set_xlabel('Month')
        ax.set_ylabel('Revenue ($)')
        ax.set_title('Monthly Revenue')
        plt.xticks(rotation=45)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close()

        return {"chart": f"data:image/png;base64,{img_base64}"}
    except Exception as e:
        return {"chart": None, "error": str(e)}

