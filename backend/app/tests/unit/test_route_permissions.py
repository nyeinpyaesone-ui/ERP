from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.models import Permission, Role
from app.routers import auth, crm, documents, finance, hr, inventory

pytestmark = pytest.mark.unit

# Each changed router must enforce its resource and action before business logic.
ROUTES = [
    (auth, "/users", "users"),
    (crm, "/companies", "companies"),
    (crm, "/contacts", "contacts"),
    (crm, "/deals", "deals"),
    (documents, "/documents", "documents"),
    (finance, "/invoices", "invoices"),
    (hr, "/departments", "departments"),
    (hr, "/employees", "employees"),
    (inventory, "/products", "products"),
    (inventory, "/movements", "inventory"),
]


@pytest.mark.parametrize("module,path,resource", ROUTES, ids=[row[2] for row in ROUTES])
@pytest.mark.parametrize("grant", ["none", "wrong-resource", "wrong-action", "correct"])
def test_list_routes_enforce_specific_read_permission(
    db: Mock,
    actor: SimpleNamespace,
    module,
    path: str,
    resource: str,
    grant: str,
) -> None:
    if grant != "none":
        actor.roles = [
            Role(
                permissions=[
                    Permission(
                        resource="unrelated" if grant == "wrong-resource" else resource,
                        action="delete" if grant == "wrong-action" else "read",
                    )
                ]
            )
        ]
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.get(path)
    if grant == "correct":
        assert response.status_code == 200
        assert response.json() == []
    else:
        assert response.status_code == 403
        assert response.json() == {"detail": f"Permission denied: {resource}.read"}
        db.query.assert_not_called()


@pytest.mark.parametrize(
    "module,method,path,permission",
    [
        (auth, "put", "/users/1", "users.update"),
        (crm, "post", "/companies", "companies.create"),
        (crm, "put", "/contacts/1", "contacts.update"),
        (crm, "delete", "/deals/1", "deals.delete"),
        (documents, "post", "/upload", "documents.create"),
        (documents, "delete", "/documents/1", "documents.delete"),
        (finance, "post", "/payments", "invoices.create"),
        (finance, "put", "/invoices/1/status?status=paid", "invoices.update"),
        (hr, "delete", "/employees/1", "employees.delete"),
        (inventory, "post", "/movements", "inventory.create"),
        (crm, "get", "/dashboard", "reports.read"),
        (finance, "get", "/dashboard", "reports.read"),
        (hr, "get", "/dashboard", "reports.read"),
        (inventory, "get", "/dashboard", "reports.read"),
    ],
)
def test_changed_write_and_report_routes_deny_unprivileged_users(
    db: Mock,
    actor: SimpleNamespace,
    module,
    method: str,
    path: str,
    permission: str,
) -> None:
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.request(method, path)
    assert response.status_code == 403
    assert response.json() == {"detail": f"Permission denied: {permission}"}
    db.add.assert_not_called()
    db.commit.assert_not_called()
