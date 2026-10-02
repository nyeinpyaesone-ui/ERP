from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Department, Employee
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()


class DepartmentCreate(BaseModel):
    name: str
    description: str | None = None
    manager_id: int | None = None
    budget: Decimal | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    manager_id: int | None = None
    budget: Decimal | None = None


class EmployeeCreate(BaseModel):
    employee_code: str
    job_title: str
    department_id: int | None = None
    salary: Decimal | None = None
    hire_date: date
    status: str = "active"
    employment_type: str = "full_time"
    address: str | None = None
    emergency_contact: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None


class EmployeeUpdate(BaseModel):
    job_title: str | None = None
    department_id: int | None = None
    salary: Decimal | None = None
    hire_date: date | None = None
    status: str | None = None
    employment_type: str | None = None
    address: str | None = None
    emergency_contact: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    job_title: str
    department_id: int | None
    salary: Decimal | None
    hire_date: date
    status: str
    employment_type: str
    address: str | None
    emergency_contact: str | None
    phone: str | None
    date_of_birth: date | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    id: int
    employee_code: str
    job_title: str
    department_id: int | None
    hire_date: date
    status: str
    employment_type: str

    class Config:
        from_attributes = True


@router.post("/departments")
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("departments", "create")),
):
    """Create, commit, and return a department."""
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    log_activity(
        db,
        user_id=current_user.id,
        action="department_created",
        entity_type="department",
        entity_id=dept.id,
    )
    return dept


@router.get("/departments")
def list_departments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("departments", "read")),
):
    """Return departments after ``skip`` records, capping ``limit`` at 100."""
    if limit > 100:
        limit = 100
    return db.query(Department).offset(skip).limit(limit).all()


@router.post("/employees")
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("employees", "create")),
):
    """Create, commit, and return an employee.

    Raise HTTP 400 if the employee code already exists.
    """
    existing = (
        db.query(Employee).filter(Employee.employee_code == data.employee_code).first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Employee code already exists")

    emp = Employee(**data.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    log_activity(
        db,
        user_id=current_user.id,
        action="employee_created",
        entity_type="employee",
        entity_id=emp.id,
    )
    return emp


@router.get("/employees")
def list_employees(
    status: str | None = None,
    department_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("employees", "read")),
):
    """Return a page of employee work details, capping ``limit`` at 100.

    ``skip`` is a record offset. Truthy status and department filters are
    matched exactly. Salary, address, phone, birth date, and emergency contact
    are omitted from each result.
    """
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
            "employment_type": e.employment_type,
        }
        for e in employees
    ]


@router.get("/employees/{employee_id}", response_model=EmployeeListResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("employees", "read")),
):
    """Return the employee work profile, or raise HTTP 404 if it does not exist.

    Returns work details only (no PII like salary, address, phone, birth date).
    Full PII fields require employees:update via the update endpoint.
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {
        "id": emp.id,
        "employee_code": emp.employee_code,
        "job_title": emp.job_title,
        "department_id": emp.department_id,
        "hire_date": emp.hire_date,
        "status": emp.status,
        "employment_type": emp.employment_type,
    }


@router.put("/employees/{employee_id}")
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("employees", "update")),
):
    """Commit explicitly supplied fields and return the updated employee.

    Omitted fields remain unchanged; explicit nulls are applied. Raise
    HTTP 404 if the employee does not exist.
    """
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
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("employees", "delete")),
):
    """Delete and commit the employee, then return a confirmation message.

    Raise HTTP 404 if the employee does not exist.
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()
    return {"message": "Employee deleted"}


@router.get("/dashboard")
def hr_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports", "read")),
):
    """Return employee and department counts with active-employee salary totals.

    ``monthly_payroll`` is the sum of stored salaries for active employees.
    The average divides that sum by all active employees and is zero if none
    are active.
    """
    total_employees = db.query(Employee).count()
    active_employees = db.query(Employee).filter(Employee.status == "active").count()
    total_departments = db.query(Department).count()
    total_payroll = db.query(func.sum(Employee.salary)).filter(
        Employee.status == "active"
    ).scalar() or Decimal("0")

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "total_departments": total_departments,
        "monthly_payroll": float(total_payroll),
        "avg_salary": (
            float(total_payroll / active_employees) if active_employees > 0 else 0
        ),
    }
