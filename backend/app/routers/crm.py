from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, Contact, Deal
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()


# Schemas
class CompanyCreate(BaseModel):
    name: str
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    address: str | None = None
    phone: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    address: str | None = None
    phone: str | None = None


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    company_id: int | None = None
    status: str = "lead"
    source: str | None = None
    notes: str | None = None


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    company_id: int | None = None
    status: str | None = None
    source: str | None = None
    notes: str | None = None


class DealCreate(BaseModel):
    title: str
    contact_id: int | None = None
    company_id: int | None = None
    value: Decimal = Decimal("0")
    stage: str = "prospect"
    probability: int = 0
    expected_close_date: date | None = None
    description: str | None = None


class DealUpdate(BaseModel):
    title: str | None = None
    value: Decimal | None = None
    stage: str | None = None
    probability: int | None = None
    expected_close_date: date | None = None
    actual_close_date: date | None = None


# Companies
@router.post("/companies")
def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("companies", "create")),
):
    """Create, commit, and return a company."""
    company = Company(**data.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    log_activity(
        db,
        user_id=current_user.id,
        action="company_created",
        entity_type="company",
        entity_id=company.id,
    )
    return company


@router.get("/companies")
def list_companies(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("companies", "read")),
):
    """Return a page of companies, capping ``limit`` at 100.

    ``skip`` is a record offset. A nonempty ``search`` matches names with a
    case-insensitive SQL LIKE pattern surrounded by wildcards.
    """
    if limit > 100:
        limit = 100
    query = db.query(Company)
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
    return query.offset(skip).limit(limit).all()


@router.get("/companies/{company_id}")
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("companies", "read")),
):
    """Return the company, or raise HTTP 404 if it does not exist."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/companies/{company_id}")
def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("companies", "update")),
):
    """Commit explicitly supplied fields and return the updated company.

    Omitted fields remain unchanged; explicit nulls are applied. Raise
    HTTP 404 if the company does not exist.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("companies", "delete")),
):
    """Delete and commit the company, then return a confirmation message.

    Raise HTTP 404 if the company does not exist.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()
    return {"message": "Company deleted"}


# Contacts
@router.post("/contacts")
def create_contact(
    data: ContactCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contacts", "create")),
):
    """Create, commit, and return a contact assigned to the current user."""
    contact = Contact(**data.model_dump(), assigned_to=current_user.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    log_activity(
        db,
        user_id=current_user.id,
        action="contact_created",
        entity_type="contact",
        entity_id=contact.id,
    )
    return contact


@router.get("/contacts")
def list_contacts(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contacts", "read")),
):
    """Return a page of contacts, capping ``limit`` at 100.

    ``skip`` is a record offset. Nonempty filters match status exactly and
    search full names or emails with a case-insensitive SQL LIKE pattern.
    """
    if limit > 100:
        limit = 100
    query = db.query(Contact)
    if status:
        query = query.filter(Contact.status == status)
    if search:
        query = query.filter(
            (Contact.first_name + " " + Contact.last_name).ilike(f"%{search}%")
            | Contact.email.ilike(f"%{search}%")
        )
    return query.offset(skip).limit(limit).all()


@router.get("/contacts/{contact_id}")
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contacts", "read")),
):
    """Return the contact, or raise HTTP 404 if it does not exist."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.put("/contacts/{contact_id}")
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contacts", "update")),
):
    """Commit explicitly supplied fields and return the updated contact.

    Omitted fields remain unchanged; explicit nulls are applied. Raise
    HTTP 404 if the contact does not exist.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contact, key, value)
    contact.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contacts", "delete")),
):
    """Delete and commit the contact, then return a confirmation message.

    Raise HTTP 404 if the contact does not exist.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "Contact deleted"}


# Deals / Pipeline
@router.post("/deals")
def create_deal(
    data: DealCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "create")),
):
    """Create, commit, and return a deal assigned to the current user."""
    deal = Deal(**data.model_dump(), assigned_to=current_user.id)
    db.add(deal)
    db.commit()
    db.refresh(deal)
    log_activity(
        db,
        user_id=current_user.id,
        action="deal_created",
        entity_type="deal",
        entity_id=deal.id,
    )
    return deal


@router.get("/deals")
def list_deals(
    skip: int = 0,
    limit: int = 100,
    stage: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "read")),
):
    """Return deals after ``skip`` records, capping ``limit`` at 100.

    A nonempty ``stage`` restricts results to that exact stage.
    """
    if limit > 100:
        limit = 100
    query = db.query(Deal)
    if stage:
        query = query.filter(Deal.stage == stage)
    return query.offset(skip).limit(limit).all()


@router.get("/deals/pipeline")
def get_pipeline(
    limit_per_stage: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "read")),
):
    """Return deal summaries, counts, and values for each predefined pipeline stage.

    ``limit_per_stage`` limits the deals fetched for each stage. Counts and
    total values describe only those fetched deals, with no specified order.
    """
    stages = [
        "prospect",
        "qualification",
        "proposal",
        "negotiation",
        "closed_won",
        "closed_lost",
    ]
    pipeline = {}
    for stage in stages:
        deals = db.query(Deal).filter(Deal.stage == stage).limit(limit_per_stage).all()
        total = sum(float(d.value or 0) for d in deals)
        pipeline[stage] = {
            "count": len(deals),
            "total_value": total,
            "deals": [
                {
                    "id": d.id,
                    "title": d.title,
                    "value": float(d.value or 0),
                    "stage": d.stage,
                }
                for d in deals
            ],
        }
    return pipeline


@router.get("/deals/{deal_id}")
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "read")),
):
    """Return the deal, or raise HTTP 404 if it does not exist."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.put("/deals/{deal_id}")
def update_deal(
    deal_id: int,
    data: DealUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "update")),
):
    """Commit supplied deal fields and return the updated deal.

    A supplied recognized stage overrides probability with its stage default.
    A won deal without a close date receives today's date, even if stage was
    not supplied. Omitted fields otherwise remain unchanged; explicit nulls
    are applied. Raise HTTP 404 if the deal does not exist.
    """
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(deal, key, value)

    # Auto-update probability based on stage
    stage_probabilities = {
        "prospect": 10,
        "qualification": 25,
        "proposal": 50,
        "negotiation": 75,
        "closed_won": 100,
        "closed_lost": 0,
    }
    if deal.stage in stage_probabilities and "stage" in update_data:
        deal.probability = stage_probabilities[deal.stage]

    if deal.stage == "closed_won" and not deal.actual_close_date:
        deal.actual_close_date = date.today()

    deal.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(deal)
    log_activity(
        db,
        user_id=current_user.id,
        action="deal_updated",
        entity_type="deal",
        entity_id=deal.id,
        details={"stage": deal.stage},
    )
    return deal


@router.delete("/deals/{deal_id}")
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("deals", "delete")),
):
    """Delete and commit the deal, then return a confirmation message.

    Raise HTTP 404 if the deal does not exist.
    """
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    db.delete(deal)
    db.commit()
    return {"message": "Deal deleted"}


# Dashboard stats
@router.get("/dashboard")
def crm_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports", "read")),
):
    """Return CRM counts, pipeline value, and the percentage of deals won.

    Pipeline value excludes only lost deals. Conversion is zero when no
    deals exist.
    """
    total_contacts = db.query(Contact).count()
    total_companies = db.query(Company).count()
    total_deals = db.query(Deal).count()
    total_pipeline_value = db.query(func.sum(Deal.value)).filter(
        Deal.stage != "closed_lost"
    ).scalar() or Decimal("0")
    won_deals = db.query(Deal).filter(Deal.stage == "closed_won").count()

    return {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "total_deals": total_deals,
        "pipeline_value": float(total_pipeline_value),
        "won_deals": won_deals,
        "conversion_rate": (won_deals / total_deals * 100) if total_deals > 0 else 0,
    }
