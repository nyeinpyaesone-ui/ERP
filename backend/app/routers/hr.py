from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.database import get_db
from app.models import Employee, Department
from app.auth import get_current_user
from app.services.permissions import require_permission
from app.services.activity_log import log_activity

router = APIRouter()

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    manager_id: Optional[int] = None
    budget: Optional[Decimal] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[int] = None
    budget: Optional[Decimal] = None

class EmployeeCreate(BaseModel):
    employee_code: str
    job_title: str
    department_id: Optional[int] = None
    salary: Optional[Decimal] = None
    hire_date: date
    status: str = "active"
    employment_type: str = "full_time"
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None

class EmployeeUpdate(BaseModel):
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    salary: Optional[Decimal] = None
    hire_date: Optional[date] = None
    status: Optional[str] = None
    employment_type: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None

class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    job_title: str
    department_id: Optional[int]
    salary: Optional[Decimal]
    hire_date: date
    status: str
    employment_type: str
    address: Optional[str]
    emergency_contact: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[date]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class EmployeeListResponse(BaseModel):
    id: int
    employee_code: str
    job_title: str
    department_id: Optional[int]
    hire_date: date
    status: str
    employment_type: str

    class Config:
        from_attributes = True

@router.post("/departments")
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("departments", "create"))):
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    log_activity(db, user_id=current_user.id, action="department_created", entity_type="department", entity_id=dept.id)
    return dept

@router.get("/departments")
def list_departments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("departments", "read"))
):
    if limit > 100:
        limit = 100
    return db.query(Department).offset(skip).limit(limit).all()

@router.post("/employees")
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db), current_user = Depends(require_permission("employees", "create"))):
    existing = db.query(Employee).filter(Employee.employee_code == data.employee_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee code already exists")

    emp = Employee(**data.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    log_activity(db, user_id=current_user.id, action="employee_created", entity_type="employee", entity_id=emp.id)
    return emp

@router.get("/employees")
def list_employees(
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("employees", "read"))
):
    if limit > 100:
        limit = 100
    query = db.query(Employee)
    if status:
        query = query.filter(Employee.status == status)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    employees = query.offset(skip).limit(limit).all()
    # Return limited fields (no PII)
    return [
        {
            "id": e.id,
            "employee_code": e.employee_code,
            "job_title": e.job_title,
            "department_id": e.department_id,
            "hire_date": e.hire_date,
            "status": e.status,
            "employment_type": e.employment_type
        }
        for e in employees
    ]

@router.get("/employees/{employee_id}")
def get_employee(employee_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("employees", "read"))):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    # Return full details for single employee (authorized access)
    return emp

@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db), current_user = Depends(require_permission("employees", "update"))):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(emp, key, value)
    emp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(emp)
    return emp

@router.delete("/employees/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("employees", "delete"))):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()
    return {"message": "Employee deleted"}

@router.get("/dashboard")
def hr_dashboard(db: Session = Depends(get_db), current_user = Depends(require_permission("reports", "read"))):
    total_employees = db.query(Employee).count()
    active_employees = db.query(Employee).filter(Employee.status == "active").count()
    total_departments = db.query(Department).count()
    total_payroll = db.query(func.sum(Employee.salary)).filter(Employee.status == "active").scalar() or Decimal("0")

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "total_departments": total_departments,
        "monthly_payroll": float(total_payroll),
        "avg_salary": float(total_payroll / active_employees) if active_employees > 0 else 0
    }