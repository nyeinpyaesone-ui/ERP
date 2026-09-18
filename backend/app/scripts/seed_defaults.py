#!/usr/bin/env python3
###############################################################################
# ERP SOLUTION — Seed Default Data
# Creates default roles, permissions, and system settings
###############################################################################

import sys
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import (
    Base, Role, Permission, RolePermission, UserRole,
    FieldPermission, DataPolicy, Setting
)

def seed_roles(db: Session):
    """Create default roles"""
    roles = [
        {"name": "superadmin", "display_name": "Super Administrator", "description": "Full system access", "is_system": True},
        {"name": "admin", "display_name": "Administrator", "description": "Administrative access", "is_system": True},
        {"name": "manager", "display_name": "Manager", "description": "Department/team management", "is_system": True},
        {"name": "user", "display_name": "Standard User", "description": "Basic user access", "is_system": True},
        {"name": "viewer", "display_name": "Viewer", "description": "Read-only access", "is_system": True},
    ]
    
    for role_data in roles:
        existing = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not existing:
            role = Role(**role_data)
            db.add(role)
            print(f"Created role: {role_data['name']}")
        else:
            print(f"Role exists: {role_data['name']}")
    
    db.commit()


def seed_permissions(db: Session):
    """Create default permissions"""
    resources = [
        "users", "companies", "contacts", "deals", "products",
        "invoices", "payments", "projects", "tasks", "documents",
        "workflows", "reports", "analytics", "settings", "integrations",
        "webhooks", "ai", "search", "notifications", "activity_logs"
    ]
    actions = ["create", "read", "update", "delete", "list", "export", "import"]
    
    for resource in resources:
        for action in actions:
            name = f"{resource}:{action}"
            existing = db.query(Permission).filter(Permission.name == name).first()
            if not existing:
                perm = Permission(
                    name=name,
                    resource=resource,
                    action=action,
                    description=f"{action.capitalize()} {resource}"
                )
                db.add(perm)
                print(f"Created permission: {name}")
    
    db.commit()


def seed_role_permissions(db: Session):
    """Assign permissions to roles"""
    # Superadmin gets all permissions
    superadmin = db.query(Role).filter(Role.name == "superadmin").first()
    admin = db.query(Role).filter(Role.name == "admin").first()
    manager = db.query(Role).filter(Role.name == "manager").first()
    user = db.query(Role).filter(Role.name == "user").first()
    viewer = db.query(Role).filter(Role.name == "viewer").first()
    
    all_perms = db.query(Permission).all()
    
    # Superadmin - all permissions
    for perm in all_perms:
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == superadmin.id,
            RolePermission.permission_id == perm.id
        ).first()
        if not existing:
            db.add(RolePermission(role_id=superadmin.id, permission_id=perm.id))
    
    # Admin - all except user management
    admin_perms = [p for p in all_perms if not p.name.startswith("users:")]
    for perm in admin_perms:
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == perm.id
        ).first()
        if not existing:
            db.add(RolePermission(role_id=admin.id, permission_id=perm.id))
    
    # Manager - CRUD on business objects
    manager_actions = ["create", "read", "update", "list", "export"]
    manager_resources = ["companies", "contacts", "deals", "products", "invoices", 
                         "projects", "tasks", "documents", "reports"]
    for resource in manager_resources:
        for action in manager_actions:
            perm = db.query(Permission).filter(Permission.name == f"{resource}:{action}").first()
            if perm:
                existing = db.query(RolePermission).filter(
                    RolePermission.role_id == manager.id,
                    RolePermission.permission_id == perm.id
                ).first()
                if not existing:
                    db.add(RolePermission(role_id=manager.id, permission_id=perm.id))
    
    # User - basic CRUD on own data
    user_perms = [
        "contacts:read", "contacts:create", "contacts:update",
        "deals:read", "deals:create", "deals:update",
        "tasks:read", "tasks:create", "tasks:update",
        "documents:read", "documents:create",
        "projects:read", "reports:read", "analytics:read",
        "search:read", "ai:read", "notifications:read"
    ]
    for perm_name in user_perms:
        perm = db.query(Permission).filter(Permission.name == perm_name).first()
        if perm:
            existing = db.query(RolePermission).filter(
                RolePermission.role_id == user.id,
                RolePermission.permission_id == perm.id
            ).first()
            if not existing:
                db.add(RolePermission(role_id=user.id, permission_id=perm.id))
    
    # Viewer - read only
    read_perms = [p for p in all_perms if p.action == "read"]
    for perm in read_perms:
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == viewer.id,
            RolePermission.permission_id == perm.id
        ).first()
        if not existing:
            db.add(RolePermission(role_id=viewer.id, permission_id=perm.id))
    
    db.commit()
    print("Role permissions assigned")


def seed_settings(db: Session):
    """Create default system settings"""
    settings = [
        {"key": "company_name", "value": "ERP SOLUTION", "category": "general", "description": "Company display name"},
        {"key": "timezone", "value": "UTC", "category": "general", "description": "Default timezone"},
        {"key": "date_format", "value": "YYYY-MM-DD", "category": "general", "description": "Default date format"},
        {"key": "currency", "value": "USD", "category": "finance", "description": "Default currency"},
        {"key": "invoice_prefix", "value": "INV", "category": "finance", "description": "Invoice number prefix"},
        {"key": "max_upload_size", "value": "52428800", "category": "system", "description": "Max upload size in bytes (50MB)"},
        {"key": "session_timeout", "value": "86400", "category": "security", "description": "Session timeout in seconds (24h)"},
        {"key": "password_min_length", "value": "8", "category": "security", "description": "Minimum password length"},
        {"key": "enable_registration", "value": "false", "category": "security", "description": "Allow user self-registration"},
        {"key": "ollama_model", "value": "llama3.1", "category": "ai", "description": "Default Ollama model"},
        {"key": "ai_temperature", "value": "0.7", "category": "ai", "description": "Default AI temperature"},
    ]
    
    for setting_data in settings:
        existing = db.query(Setting).filter(Setting.key == setting_data["key"]).first()
        if not existing:
            setting = Setting(**setting_data)
            db.add(setting)
            print(f"Created setting: {setting_data['key']}")
    
    db.commit()


def main():
    print("==========================================")
    print("ERP SOLUTION — Seeding Default Data")
    print("==========================================")
    
    db = SessionLocal()
    try:
        seed_roles(db)
        seed_permissions(db)
        seed_role_permissions(db)
        seed_settings(db)
        print("==========================================")
        print("Seeding completed successfully!")
        print("==========================================")
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()