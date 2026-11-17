from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, text
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Invoice, Deal, Contact, Product, Employee, Project, Task, ActivityLog
from app.auth import get_current_user

router = APIRouter()

@router.get("/dashboard")
def get_dashboard_analytics(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Optimized dashboard using single aggregated query instead of 12+ separate queries."""
    
    # Single query to fetch all scalar counts and sums efficiently
    result = db.execute(text("""
        SELECT 
            (SELECT COALESCE(SUM(total), 0) FROM invoices WHERE status = 'paid') as total_revenue,
            (SELECT COALESCE(SUM(total - amount_paid), 0) FROM invoices WHERE status != 'paid') as outstanding,
            (SELECT COUNT(*) FROM contacts) as total_contacts,
            (SELECT COUNT(*) FROM deals) as total_deals,
            (SELECT COALESCE(SUM(value), 0) FROM deals WHERE stage != 'closed_lost') as pipeline_value,
            (SELECT COUNT(*) FROM employees) as total_employees,
            (SELECT COUNT(*) FROM employees WHERE status = 'active') as active_employees,
            (SELECT COUNT(*) FROM products) as total_products,
            (SELECT COUNT(*) FROM products WHERE quantity_in_stock <= reorder_level) as low_stock,
            (SELECT COUNT(*) FROM projects) as total_projects,
            (SELECT COUNT(*) FROM projects WHERE status = 'active') as active_projects,
            (SELECT COUNT(*) FROM tasks) as total_tasks,
            (SELECT COUNT(*) FROM tasks WHERE status = 'done') as completed_tasks
    """)).first()
    
    # Fetch recent activity separately (limited dataset)
    recent_activity = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    total_revenue = float(result.total_revenue or 0)
    outstanding = float(result.outstanding or 0)
    total_contacts = result.total_contacts or 0
    total_deals = result.total_deals or 0
    pipeline_value = float(result.pipeline_value or 0)
    total_employees = result.total_employees or 0
    active_employees = result.active_employees or 0
    total_products = result.total_products or 0
    low_stock = result.low_stock or 0
    total_projects = result.total_projects or 0
    active_projects = result.active_projects or 0
    total_tasks = result.total_tasks or 0
    completed_tasks = result.completed_tasks or 0
    
    collection_rate = (total_revenue / (total_revenue + outstanding) * 100) if (total_revenue + outstanding) > 0 else 0.0
    
    return {
        "revenue": {
            "total": total_revenue,
            "outstanding": outstanding,
            "collection_rate": round(collection_rate, 2)
        },
        "crm": {
            "contacts": total_contacts,
            "deals": total_deals,
            "pipeline_value": pipeline_value
        },
        "hr": {
            "total_employees": total_employees,
            "active_employees": active_employees
        },
        "inventory": {
            "total_products": total_products,
            "low_stock": low_stock
        },
        "projects": {
            "total_projects": total_projects,
            "active_projects": active_projects,
            "tasks": {"total": total_tasks, "completed": completed_tasks}
        },
        "recent_activity": [
            {"action": a.action, "entity_type": a.entity_type, "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in recent_activity
        ]
    }

@router.get("/monthly-trends")
def get_monthly_trends(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    months_back = 6
    start_date = datetime.now() - timedelta(days=30 * months_back)

    revenue_by_month = db.query(
        extract('year', Invoice.issue_date).label('year'),
        extract('month', Invoice.issue_date).label('month'),
        func.sum(Invoice.total).label('total')
    ).filter(Invoice.issue_date >= start_date).group_by('year', 'month').order_by('year', 'month').all()

    deals_by_month = db.query(
        extract('year', Deal.created_at).label('year'),
        extract('month', Deal.created_at).label('month'),
        func.count(Deal.id).label('count'),
        func.sum(Deal.value).label('value')
    ).filter(Deal.created_at >= start_date).group_by('year', 'month').order_by('year', 'month').all()

    return {
        "revenue": [
            {"period": f"{r.year}-{r.month:02d}", "amount": float(r.total)}
            for r in revenue_by_month
        ],
        "deals": [
            {"period": f"{d.year}-{d.month:02d}", "count": d.count, "value": float(d.value or 0)}
            for d in deals_by_month
        ]
    }

