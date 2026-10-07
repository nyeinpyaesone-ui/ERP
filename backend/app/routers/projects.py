from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Task
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "planning"
    priority: str = "medium"
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    client_id: int | None = None


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str | None = None
    status: str = "todo"
    priority: str = "medium"
    assigned_to: int | None = None
    due_date: date | None = None
    estimated_hours: float | None = None
    parent_task_id: int | None = None


@router.post("/projects")
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("projects", "create")),
):
    project = Project(**data.dict(), manager_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    log_activity(
        db,
        user_id=current_user.id,
        action="project_created",
        entity_type="project",
        entity_id=project.id,
    )
    return project


@router.get("/projects")
def list_projects(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("projects", "read")),
):
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    return query.all()


@router.get("/projects/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("projects", "read")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/projects/{project_id}")
def update_project(
    project_id: int,
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("projects", "update")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, value in data.dict().items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.post("/tasks")
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("tasks", "create")),
):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(**data.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    log_activity(
        db,
        user_id=current_user.id,
        action="task_created",
        entity_type="task",
        entity_id=task.id,
    )
    return task


@router.get("/projects/{project_id}/tasks")
def list_project_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("tasks", "read")),
):
    return db.query(Task).filter(Task.project_id == project_id).all()


@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("tasks", "update")),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in data.items():
        if hasattr(task, key):
            setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@router.get("/dashboard")
def projects_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("reports", "read")),
):
    total_projects = db.query(Project).count()
    active_projects = db.query(Project).filter(Project.status == "active").count()
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == "done").count()

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": (
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        ),
    }
