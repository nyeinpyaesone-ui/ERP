from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
import httpx
import json
from datetime import datetime

from app.database import get_db
from app.models import Contact, Company, Deal, Product, Invoice, Project, Task
from app.auth import get_current_user
from app.config import settings
from app.services.activity_log import log_activity

router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    context: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None

async def query_ollama(prompt: str, model: str = None) -> str:
    model = model or settings.OLLAMA_MODEL
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "No response from AI")
            return f"AI service unavailable (status: {response.status_code})"
    except Exception as e:
        return f"AI service error: {str(e)}"

@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Gather business context
    context_data = {}

    # Recent contacts - optimized with limit
    context_data["contacts_count"] = db.query(Contact).count()
    context_data["recent_contacts"] = [
        {"name": f"{c.first_name} {c.last_name}", "status": c.status}
        for c in db.query(Contact).order_by(Contact.created_at.desc()).limit(5).all()
    ]

    # Pipeline - optimized: use aggregated query instead of loading all deals
    pipeline_stats = db.query(
        Deal.stage,
        func.count(Deal.id).label("count"),
        func.sum(Deal.value).label("total_value")
    ).group_by(Deal.stage).all()
    
    pipeline_dict = {row.stage: {"count": row.count, "value": float(row.total_value or 0)} for row in pipeline_stats}
    total_pipeline_value = sum(v["value"] for k, v in pipeline_dict.items() if k != "closed_lost")
    
    context_data["pipeline_value"] = total_pipeline_value
    context_data["deals_by_stage"] = {
        stage: pipeline_dict.get(stage, {"count": 0, "value": 0.0})
        for stage in ["prospect", "qualification", "proposal", "negotiation", "closed_won", "closed_lost"]
    }

    # Inventory - optimized: use aggregated queries instead of loading all products
    inventory_stats = db.query(
        func.count(Product.id).label("total"),
        func.sum(func.case((Product.quantity_in_stock <= Product.reorder_level, 1), else_=0)).label("low_stock_count")
    ).first()
    
    low_stock_items = db.query(Product).filter(
        Product.quantity_in_stock <= Product.reorder_level
    ).limit(5).all()
    
    context_data["total_products"] = inventory_stats.total or 0
    context_data["low_stock_count"] = inventory_stats.low_stock_count or 0
    context_data["low_stock_items"] = [
        {"name": p.name, "stock": p.quantity_in_stock, "reorder": p.reorder_level}
        for p in low_stock_items
    ]

    # Projects - optimized: use aggregated queries instead of loading all tasks
    task_stats = db.query(
        func.count(Task.id).label("total"),
        func.sum(func.case((Task.due_date < datetime.now().date()) & (Task.status != "done"), 1), else_=0).label("overdue")
    ).first()
    
    context_data["total_tasks"] = task_stats.total or 0
    context_data["overdue_tasks"] = task_stats.overdue or 0

    prompt = f"""You are an AI business assistant for an ERP system. Answer the user's question concisely and helpfully.

Business Context:
{json.dumps(context_data, indent=2, default=str)}

User Question: {message.message}

Provide a helpful, data-driven response. If you don't have specific data, say so."""

    response_text = await query_ollama(prompt)

    log_activity(db, user_id=current_user.id, action="ai_chat", entity_type="ai", details={"query": message.message[:200]})

    return ChatResponse(response=response_text)

@router.get("/insights")
async def get_ai_insights(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from datetime import timedelta

    # Revenue insights - optimized: use SUM instead of loading all invoices
    last_month = datetime.now() - timedelta(days=30)
    revenue_result = db.query(func.sum(Invoice.total)).filter(
        Invoice.created_at >= last_month
    ).scalar() or 0

    # Churn risk - optimized: use COUNT instead of loading all contacts
    inactive_count = db.query(Contact).filter(
        Contact.last_activity < datetime.now() - timedelta(days=90)
    ).count()

    # Stock alerts - optimized: use COUNT and limit results
    low_stock_count = db.query(Product).filter(
        Product.quantity_in_stock <= Product.reorder_level
    ).count()
    
    low_stock_items = db.query(Product.name, Product.quantity_in_stock, Product.reorder_level).filter(
        Product.quantity_in_stock <= Product.reorder_level
    ).limit(5).all()

    insights = []

    if revenue_result > 0:
        insights.append({
            "category": "revenue",
            "priority": "medium",
            "message": f"Revenue in last 30 days: ${revenue_result:,.2f}"
        })

    if inactive_count > 0:
        insights.append({
            "category": "growth",
            "priority": "high",
            "message": f"{inactive_count} contacts have been inactive for 90+ days. Consider re-engagement campaigns."
        })

    if low_stock_count > 0:
        insights.append({
            "category": "operations",
            "priority": "high",
            "message": f"{low_stock_count} products are below reorder level. Restock recommended."
        })

    # Get AI-generated summary - optimized: use COUNT instead of full queries
    total_deals = db.query(Deal).count()
    active_projects = db.query(Project).filter(Project.status == 'active').count()
    
    prompt = f"""Analyze this business data and provide 3-5 actionable insights:
- Revenue last 30 days: ${revenue_result:,.2f}
- Inactive contacts: {inactive_count}
- Low stock products: {low_stock_count}
- Total deals: {total_deals}
- Active projects: {active_projects}

Format as JSON with fields: category, priority, message."""

    ai_response = await query_ollama(prompt)

    return {
        "insights": insights,
        "ai_summary": ai_response,
        "health_score": "good" if len([i for i in insights if i["priority"] == "high"]) < 3 else "fair"
    }

@router.get("/forecast/revenue")
async def forecast_revenue(
    months: int = 3,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from datetime import timedelta

    # Get last 6 months of paid invoices
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    monthly_data = db.query(
        func.extract('month', Invoice.created_at).label('month'),
        func.extract('year', Invoice.created_at).label('year'),
        func.sum(Invoice.total).label('total')
    ).filter(
        Invoice.created_at >= start_date,
        Invoice.status == "paid"
    ).group_by('year', 'month').order_by('year', 'month').all()

    if not monthly_data:
        return {"forecast": [], "message": "Insufficient data for forecasting"}

    values = [float(m.total) for m in monthly_data]
    avg_growth = sum((values[i] - values[i-1]) / values[i-1] * 100 for i in range(1, len(values))) / max(1, len(values) - 1) if len(values) > 1 else 0

    forecast = []
    last_value = values[-1] if values else 0

    for i in range(1, months + 1):
        predicted = last_value * (1 + avg_growth / 100) ** i
        forecast.append({
            "month": i,
            "predicted_revenue": round(predicted, 2),
            "confidence_low": round(predicted * 0.8, 2),
            "confidence_high": round(predicted * 1.2, 2),
            "growth_rate": round(avg_growth, 2)
        })

    return {
        "historical": [{"month": f"{m.year}-{m.month}", "revenue": float(m.total)} for m in monthly_data],
        "forecast": forecast,
        "trend": "increasing" if avg_growth > 0 else "decreasing" if avg_growth < 0 else "stable",
        "confidence": "medium"
    }

