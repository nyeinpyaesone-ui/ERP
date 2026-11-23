"""Focused unit tests for role-management route behavior."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.routers import permissions


@pytest.fixture
def role_db():
    engine = create_engine("sqlite:///:memory:")
    tables = [
        models.Tenant.__table__,
        models.User.__table__,
        models.Role.__table__,
        models.Permission.__table__,
        models.RolePermission.__table__,
        models.UserRole.__table__,
    ]
    models.Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def admin():
    return SimpleNamespace(id=1)


def test_create_role_and_reject_duplicate(role_db, admin, monkeypatch):
    monkeypatch.setattr(permissions, "log_activity", lambda *args, **kwargs: None)

    created = permissions.create_role(
        permissions.RoleCreate(
            name="auditor", display_name="Auditor", description="Read-only audit"
        ),
        role_db,
        admin,
    )

    assert created.name == "auditor"
    assert created.description == "Read-only audit"
    with pytest.raises(HTTPException) as error:
        permissions.create_role(
            permissions.RoleCreate(name="auditor", display_name="Duplicate"),
            role_db,
            admin,
        )
    assert error.value.status_code == 400


def test_list_roles_includes_assigned_permissions(role_db, admin):
    role = models.Role(name="operator", display_name="Operator")
    permission = models.Permission(
        name="orders:read", resource="orders", action="read"
    )
    role.permissions.append(permission)
    role_db.add(role)
    role_db.commit()

    result = permissions.list_roles(role_db, admin)

    assert len(result) == 1
    assert result[0].name == "operator"
    assert [item.name for item in result[0].permissions] == ["orders:read"]


def test_get_role_returns_role_or_404(role_db, admin):
    role = models.Role(name="manager", display_name="Manager")
    role_db.add(role)
    role_db.commit()

    assert permissions.get_role(role.id, role_db, admin).name == "manager"
    with pytest.raises(HTTPException) as error:
        permissions.get_role(999, role_db, admin)
    assert error.value.status_code == 404


def test_update_role_rejects_missing_and_system_roles(role_db, admin):
    with pytest.raises(HTTPException) as missing:
        permissions.update_role(
            999, permissions.RoleUpdate(display_name="New"), role_db, admin
        )
    assert missing.value.status_code == 404

    system_role = models.Role(name="system", display_name="System", is_system=True)
    custom_role = models.Role(name="custom", display_name="Custom", is_system=False)
    role_db.add_all([system_role, custom_role])
    role_db.commit()

    with pytest.raises(HTTPException) as protected:
        permissions.update_role(
            system_role.id,
            permissions.RoleUpdate(display_name="Changed"),
            role_db,
            admin,
        )
    assert protected.value.status_code == 400

    updated = permissions.update_role(
        custom_role.id,
        permissions.RoleUpdate(
            display_name="Updated", description="Updated details"
        ),
        role_db,
        admin,
    )
    assert updated.display_name == "Updated"
    assert updated.description == "Updated details"


def test_delete_role_rejects_missing_and_system_roles(role_db, admin, monkeypatch):
    monkeypatch.setattr(permissions, "log_activity", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as missing:
        permissions.delete_role(999, role_db, admin)
    assert missing.value.status_code == 404

    system_role = models.Role(name="system", display_name="System", is_system=True)
    custom_role = models.Role(name="custom", display_name="Custom")
    role_db.add_all([system_role, custom_role])
    role_db.commit()

    with pytest.raises(HTTPException) as protected:
        permissions.delete_role(system_role.id, role_db, admin)
    assert protected.value.status_code == 400

    result = permissions.delete_role(custom_role.id, role_db, admin)
    assert result == {"message": "Role deleted"}
    assert role_db.query(models.Role).filter_by(name="custom").first() is None
