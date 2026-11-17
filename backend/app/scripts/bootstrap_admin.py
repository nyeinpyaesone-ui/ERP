#!/usr/bin/env python3
###############################################################################
# ERP SOLUTION — Bootstrap Admin User
# Creates the first superadmin user and assigns the superadmin role.
# Run after initial migration: python -m app.scripts.bootstrap_admin --email admin@example.com --password 'securepassword'
###############################################################################

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.auth import get_password_hash
from app.database import SessionLocal
from app.models import Role, User


def bootstrap_admin(email: str, password: str, full_name: str, db: Session) -> User:
    """Create or upgrade a user to superadmin with the superadmin role."""

    # Check if user already exists
    user = db.query(User).filter(User.email == email).first()

    if user:
        print(f"User {email} already exists, upgrading to superadmin...")
    else:
        # Create new user
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role="superadmin",
            is_active=True,
        )
        db.add(user)
        db.flush()
        print(f"Created user: {email}")

    # Ensure superadmin role exists
    superadmin_role = db.query(Role).filter(Role.name == "superadmin").first()
    if not superadmin_role:
        raise ValueError("superadmin role not found. Run seed_defaults.py first.")

    # Assign superadmin role if not already assigned
    role_assigned = False
    for role in user.roles:
        if role.name == "superadmin":
            print(f"User {email} already has superadmin role")
            role_assigned = True
            break

    if not role_assigned:
        user.roles.append(db.query(Role).filter(Role.name == "superadmin").first())
        print(f"Assigned superadmin role to {email}")

    # Ensure role column matches
    user.role = "superadmin"
    user.is_active = True

    db.commit()
    db.refresh(user)
    print(f"User {email} is now a superadmin")
    return user


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap the first superadmin user",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.scripts.bootstrap_admin --email admin@example.com --password 'securepass'
  python -m app.scripts.bootstrap_admin --email admin@example.com  # prompts for password
        """,
    )
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", help="Admin password (prompted if not provided)")
    parser.add_argument(
        "--full-name",
        default="System Administrator",
        help="Full name for the admin user",
    )

    args = parser.parse_args()

    if not args.password:
        args.password = getpass.getpass("Enter admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if args.password != confirm:
            print("Error: Passwords do not match")
            sys.exit(1)

    if len(args.password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    print("==========================================")
    print("ERP SOLUTION — Bootstrap Admin User")
    print("==========================================")

    db = SessionLocal()
    try:
        user = bootstrap_admin(args.email, args.password, args.full_name, db)
        print("==========================================")
        print(f"Successfully bootstrapped superadmin: {user.email}")
        print("==========================================")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
