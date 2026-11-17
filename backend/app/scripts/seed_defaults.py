#!/usr/bin/env python3
###############################################################################
# ERP SOLUTION — Seed Default Data
# Creates default roles, permissions, and system settings
# Uses app/permissions_catalogue as the single source of truth
###############################################################################

import sys

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Permission, Role, Setting
from app.permissions_catalogue import (
    ROLE_GRANTS,
    SYSTEM_ROLES,
    get_actions_for_resource,
    get_resources,
)


def seed_roles(db: Session):
    """Create default roles"""
    for role_data in SYSTEM_ROLES:
        existing = db.query(Role).filter(Role.name == role_data).first()
        if not existing:
            role = Role(
                name=role_data,
                display_name=role_data.title(),
                description="",
                is_system=True,
            )
            db.add(role)
            print(f"Created role: {role_data}")
        else:
            print(f"Role exists: {role_data}")

    db.commit()


def seed_permissions(db: Session):
    """Create default permissions from the catalogue"""
    for resource in get_resources():
        for action in get_actions_for_resource(resource):
            name = f"{resource}:{action}"
            existing = db.query(Permission).filter(Permission.name == name).first()
            if not existing:
                desc = f"{action.capitalize()} {resource.replace('_', ' ')}"
                perm = Permission(
                    name=name, resource=resource, action=action, description=desc
                )
                db.add(perm)
                print(f"Created permission: {name}")

    db.commit()


def seed_role_permissions(db: Session):
    """Assign permissions to roles from the catalogue grants"""
    # Fetch role objects
    roles = {
        role.name: role
        for role in db.query(Role).filter(Role.name.in_(SYSTEM_ROLES)).all()
    }

    # Get all permissions from DB
    all_perms = {perm.name: perm.id for perm in db.query(Permission).all()}

    for grant in ROLE_GRANTS:
        role = roles.get(grant.role_name)
        if not role:
            print(f"Warning: Role {grant.role_name} not found, skipping")
            continue

        role_perm_ids = {rp.id for rp in role.permissions}

        for perm_name in grant.permissions:
            perm_id = all_perms.get(perm_name)
            if not perm_id:
                print(f"Warning: Permission '{perm_name}' not found in DB, skipping")
                continue

            if perm_id not in role_perm_ids:
                from app.models import RolePermission

                db.add(RolePermission(role_id=role.id, permission_id=perm_id))

    db.commit()
    print("Role permissions assigned from catalogue grants")


def seed_settings(db: Session):
    """Create default system settings"""
    settings = [
        {
            "key": "company_name",
            "value": "ERP SOLUTION",
            "category": "general",
            "description": "Company display name",
        },
        {
            "key": "timezone",
            "value": "UTC",
            "category": "general",
            "description": "Default timezone",
        },
        {
            "key": "date_format",
            "value": "YYYY-MM-DD",
            "category": "general",
            "description": "Default date format",
        },
        {
            "key": "currency",
            "value": "USD",
            "category": "finance",
            "description": "Default currency",
        },
        {
            "key": "invoice_prefix",
            "value": "INV",
            "category": "finance",
            "description": "Invoice number prefix",
        },
        {
            "key": "max_upload_size",
            "value": "52428800",
            "category": "system",
            "description": "Max upload size in bytes (50MB)",
        },
        {
            "key": "session_timeout",
            "value": "86400",
            "category": "security",
            "description": "Session timeout in seconds (24h)",
        },
        {
            "key": "password_min_length",
            "value": "8",
            "category": "security",
            "description": "Minimum password length",
        },
        {
            "key": "enable_registration",
            "value": "false",
            "category": "security",
            "description": "Allow user self-registration",
        },
        {
            "key": "ollama_model",
            "value": "llama3.1",
            "category": "ai",
            "description": "Default Ollama model",
        },
        {
            "key": "ai_temperature",
            "value": "0.7",
            "category": "ai",
            "description": "Default AI temperature",
        },
    ]

    for setting_data in settings:
        existing = db.query(Setting).filter(Setting.key == setting_data["key"]).first()
        if not existing:
            setting = Setting(**setting_data)
            db.add(setting)
            print(f"Created setting: {setting_data['key']}")

    db.commit()


def main():
    """Seed roles, permissions, role assignments, and settings, then close the session.

    Each seeding step commits separately. On a seeding error, roll back the
    current transaction and exit with status 1; earlier commits remain.
    """
    print("==========================================")
    print("ERP SOLUTION — Seeding Default Data (from Catalogue)")
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
