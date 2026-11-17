"""Small SQLite integration tests for relationship joins and idempotent seeding."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Permission, Role, RolePermission, Setting, User, UserRole
from app.permissions_catalogue import ALL_PERMISSIONS
from app.scripts import seed_defaults

pytestmark = pytest.mark.integration


@pytest.fixture
def rbac_db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        model.__table__
        for model in (User, Role, Permission, RolePermission, UserRole, Setting)
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_role_membership_uses_assignee_not_assigning_administrator(
    rbac_db: Session,
) -> None:
    assigner = User(
        email="assigner@example.com", full_name="Assigner", hashed_password="synthetic"
    )
    member = User(
        email="member@example.com", full_name="Member", hashed_password="synthetic"
    )
    role = Role(name="manager", display_name="Manager")
    rbac_db.add_all([assigner, member, role])
    rbac_db.flush()
    assignment = UserRole(user_id=member.id, role_id=role.id, assigned_by=assigner.id)
    rbac_db.add(assignment)
    rbac_db.commit()
    rbac_db.expire_all()

    assert member.roles == [role]
    assert role.users == [member]
    assert assigner.roles == []
    assert assignment.role is role
    assert assignment.assigned_by_user is assigner

    member.roles.remove(role)
    rbac_db.commit()
    rbac_db.expire_all()
    assert role.users == []
    assert rbac_db.query(UserRole).count() == 0
    assert rbac_db.query(User).count() == 2


def test_seed_is_repeatable_and_preserves_customized_settings(rbac_db: Session) -> None:
    rbac_db.add(Setting(key="currency", value="EUR", category="finance"))
    rbac_db.commit()
    for _ in range(2):
        seed_defaults.seed_roles(rbac_db)
        seed_defaults.seed_permissions(rbac_db)
        seed_defaults.seed_role_permissions(rbac_db)
        seed_defaults.seed_settings(rbac_db)
        rbac_db.expire_all()
        assert rbac_db.query(Role).count() == 5
        assert rbac_db.query(Permission).count() == len(ALL_PERMISSIONS)
        assert rbac_db.query(Setting).count() == 11
        assert rbac_db.query(Setting).filter_by(key="currency").one().value == "EUR"
        assignments = rbac_db.query(RolePermission).all()
        assert len(assignments) == len(
            {(item.role_id, item.permission_id) for item in assignments}
        )

    roles = {
        role.name: {perm.name for perm in role.permissions}
        for role in rbac_db.query(Role).all()
    }
    all_permissions = {perm.name for perm in rbac_db.query(Permission).all()}
    assert roles["superadmin"] == all_permissions
    # Admin holds everything except the one superadmin-only grant (see catalogue).
    assert roles["admin"] == all_permissions - {"migrations:manage"}
    assert roles["viewer"] == {
        name for name in all_permissions if name.endswith(":read")
    }
    assert "invoices:create" in roles["manager"]
    assert not any(
        name.endswith(":delete") or name.startswith("users:")
        for name in roles["manager"]
    )
    assert "contacts:create" in roles["user"]
    assert "users:update" not in roles["user"]
    assert "invoices:create" not in roles["user"]
