"""
Permission Catalogue — Single Source of Truth for RBAC

This module declares the complete permission catalogue as data structures.
All other parts of the system (migrations, seeders, runtime checks, tests)
should derive from this catalogue. Do not hard-code resource/action strings
anywhere else.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    """A single permission: resource + action."""

    resource: str
    action: str
    description: str = ""

    @property
    def name(self) -> str:
        """Canonical permission name: resource:action"""
        return f"{self.resource}:{self.action}"


@dataclass(frozen=True)
class RolePermGrant:
    """A grant of permissions to a role."""

    role_name: str
    permissions: tuple[str, ...]  # list of permission names (resource:action)


# ─────────────────────────────────────────────────────────────────────────────
# DECLARATIVE CATALOGUE
# ─────────────────────────────────────────────────────────────────────────────

# All resources in the system. Keep sorted for readability.
RESOURCES: tuple[str, ...] = (
    "activity_logs",
    "ai",
    "analytics",
    "companies",
    "contacts",
    "deals",
    "departments",
    "documents",
    "employees",
    "integrations",
    "invoices",
    "inventory",
    "migrations",
    "notifications",
    "payments",
    "products",
    "projects",
    "reports",
    "search",
    "settings",
    "tasks",
    "users",
    "webhooks",
    "workflows",
)

# Standard CRUD+ actions available on most resources
STANDARD_ACTIONS: tuple[str, ...] = (
    "create",
    "read",
    "update",
    "delete",
    "list",
)

# Resource-specific additional actions
RESOURCE_EXTRA_ACTIONS: dict[str, tuple[str, ...]] = {
    "invoices": ("export", "import"),
    "products": ("export", "import"),
    "contacts": ("export", "import"),
    "reports": ("export",),
    "analytics": ("export",),
    "documents": ("export",),
    "inventory": ("adjust",),
    "payments": ("refund",),
    "webhooks": ("test",),
    "migrations": ("manage",),
    "integrations": ("test",),
}

# System roles (must match seed_defaults.py role names)
SYSTEM_ROLES: tuple[str, ...] = (
    "superadmin",
    "admin",
    "manager",
    "user",
    "viewer",
)

# Role permission grants — what each role gets by default
ROLE_GRANTS: tuple[RolePermGrant, ...] = (
    # superadmin: everything
    RolePermGrant(
        role_name="superadmin",
        permissions=tuple(f"{r}:{a}" for r in RESOURCES for a in STANDARD_ACTIONS)
        + tuple(f"{r}:{a}" for r, acts in RESOURCE_EXTRA_ACTIONS.items() for a in acts),
    ),
    # admin: everything except migrations.manage
    RolePermGrant(
        role_name="admin",
        permissions=tuple(f"{r}:{a}" for r in RESOURCES for a in STANDARD_ACTIONS)
        + tuple(
            f"{r}:{a}"
            for r, acts in RESOURCE_EXTRA_ACTIONS.items()
            for a in acts
            if not (r == "migrations" and a == "manage")
        ),
    ),
    # manager: read/create/update on most resources
    RolePermGrant(
        role_name="manager",
        permissions=tuple(
            f"{r}:{a}"
            for r in RESOURCES
            for a in ("read", "create", "update", "list")
            if r not in ("users", "settings", "migrations", "admin")
        ),
    ),
    # user: basic CRUD on core resources. Finance stays read-only — the
    # frontend already gates /finance to admin/manager, so grant writes only
    # to those roles.
    RolePermGrant(
        role_name="user",
        permissions=tuple(
            f"{r}:{a}"
            for r in RESOURCES
            for a in ("read", "create", "update")
            if r
            not in (
                "users",
                "settings",
                "migrations",
                "admin",
                "integrations",
                "webhooks",
            )
            and not (r in ("invoices", "payments") and a in ("create", "update"))
        ),
    ),
    # viewer: read-only
    RolePermGrant(
        role_name="viewer",
        permissions=tuple(f"{r}:read" for r in RESOURCES),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# DERIVED DATA (computed at import time)
# ─────────────────────────────────────────────────────────────────────────────

# All permission names in the system
ALL_PERMISSIONS: tuple[str, ...] = tuple(
    f"{r}:{a}" for r in RESOURCES for a in STANDARD_ACTIONS
) + tuple(f"{r}:{a}" for r, acts in RESOURCE_EXTRA_ACTIONS.items() for a in acts)

# Permissions per role (role_name -> set of permission names)
ROLE_PERMISSIONS: dict[str, set[str]] = {
    grant.role_name: set(grant.permissions) for grant in ROLE_GRANTS
}

# Resources by category (for documentation/UI)
CORE_RESOURCES = ("users", "companies", "contacts", "deals", "products", "invoices")
HR_RESOURCES = ("employees", "departments")
INVENTORY_RESOURCES = ("inventory", "products")
FINANCE_RESOURCES = ("invoices", "payments")
PROJECT_RESOURCES = ("projects", "tasks")
AI_RESOURCES = ("ai", "analytics", "search")
ADMIN_RESOURCES = (
    "users",
    "settings",
    "migrations",
    "admin",
    "integrations",
    "webhooks",
    "notifications",
    "activity_logs",
    "documents",
    "workflows",
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def get_all_permissions() -> tuple[str, ...]:
    """Return all permission names in the system."""
    return ALL_PERMISSIONS


def get_role_permissions(role_name: str) -> set[str]:
    """Return all permissions granted to a role."""
    return ROLE_PERMISSIONS.get(role_name, set())


def get_resources() -> tuple[str, ...]:
    """Return all declared resources."""
    return RESOURCES


def get_actions_for_resource(resource: str) -> tuple[str, ...]:
    """Return all actions defined for a resource."""
    base = STANDARD_ACTIONS
    extra = RESOURCE_EXTRA_ACTIONS.get(resource, ())
    return base + extra


def validate_permission(resource: str, action: str) -> bool:
    """Check if a resource:action pair exists in the catalogue."""
    if resource not in RESOURCES:
        return False
    return action in get_actions_for_resource(resource)


def get_all_resources_with_actions() -> dict[str, tuple[str, ...]]:
    """Return mapping of resource -> all its actions."""
    return {r: get_actions_for_resource(r) for r in RESOURCES}
