"""Exercise the legacy 005 Alembic stamp compatibility paths on PostgreSQL.

The historical repository had two different migrations with revision ID 005:
the permissions reconciliation and the tenancy schema. Existing databases can
therefore have the same Alembic stamp with different physical schemas.

These tests create isolated PostgreSQL schemas, simulate both states, upgrade
to head, and verify that existing tenancy data and permission rows survive.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _run_alembic(backend_dir: Path, database_url: str, *args: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        f"Alembic command {' '.join(args)} failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@pytest.mark.parametrize("tenancy_already_applied", [False, True])
def test_legacy_005_stamp_upgrades_without_losing_tenant_data(
    tenancy_already_applied: bool,
) -> None:
    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        pytest.skip("DATABASE_URL is not configured")
    base_url = make_url(raw_url)
    if base_url.get_backend_name() != "postgresql":
        pytest.skip("Legacy migration compatibility test requires PostgreSQL")
    base_url = base_url.set(drivername="postgresql+psycopg2")

    backend_dir = Path(__file__).resolve().parents[2]
    schema = f"legacy_005_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(base_url)
    schema_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        query = dict(base_url.query)
        query["options"] = f"-csearch_path={schema}"
        isolated_url = base_url.set(query=query).render_as_string(hide_password=False)
        schema_engine = create_engine(isolated_url)

        # Both historical installations had completed the canonical 005
        # permission migration. One also had the tenancy migration applied.
        _run_alembic(backend_dir, isolated_url, "upgrade", "005")
        if tenancy_already_applied:
            _run_alembic(backend_dir, isolated_url, "upgrade", "005_tenancy")
            with schema_engine.begin() as connection:
                connection.execute(text("""
                    INSERT INTO tenants (
                        name, subdomain, schema_name,
                        subscription_start, subscription_end
                    )
                    VALUES (
                        'Legacy tenant', 'legacy', 'tenant_legacy',
                        DATE '2024-01-01', DATE '2099-12-31'
                    )
                """))
                # Simulate a legacy installation where the tenancy revision
                # was stamped as 005 and this permission was missing.
                connection.execute(
                    text("DELETE FROM permissions WHERE name = 'webhooks:test'")
                )
                connection.execute(
                    text("UPDATE alembic_version SET version_num = '005'")
                )

        _run_alembic(backend_dir, isolated_url, "upgrade", "head")
        # A second invocation must be a no-op.
        _run_alembic(backend_dir, isolated_url, "upgrade", "head")

        with schema_engine.connect() as connection:
            tenant_count = connection.execute(
                text("SELECT COUNT(*) FROM tenants WHERE name = 'Legacy tenant'")
            ).scalar_one()
            permission_count = connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE name = 'webhooks:test'")
            ).scalar_one()
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert tenant_count == (1 if tenancy_already_applied else 0)
        assert permission_count == 1
        assert version == "010"
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.mark.parametrize("legacy_stamp", ["006", "007", "008"])
def test_later_legacy_stamps_reconcile_missing_tenancy_and_permissions(
    legacy_stamp: str,
) -> None:
    """Later historical stamps must not bypass the compatibility repair."""
    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        pytest.skip("DATABASE_URL is not configured")
    base_url = make_url(raw_url)
    if base_url.get_backend_name() != "postgresql":
        pytest.skip("Legacy migration compatibility test requires PostgreSQL")
    base_url = base_url.set(drivername="postgresql+psycopg2")

    backend_dir = Path(__file__).resolve().parents[2]
    schema = f"legacy_{legacy_stamp}_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(base_url)
    schema_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        query = dict(base_url.query)
        query["options"] = f"-csearch_path={schema}"
        isolated_url = base_url.set(query=query).render_as_string(hide_password=False)
        schema_engine = create_engine(isolated_url)

        _run_alembic(backend_dir, isolated_url, "upgrade", legacy_stamp)
        with schema_engine.begin() as connection:
            # Model an installation stamped by a later historical revision
            # before the duplicate-005 repair was introduced.
            connection.execute(text("""
                DROP TABLE IF EXISTS
                    purchase_order_items,
                    po_approvals,
                    transaction_logs,
                    purchase_orders,
                    vendors,
                    tenants
                CASCADE
            """))
            connection.execute(
                text("ALTER TABLE users DROP COLUMN IF EXISTS tenant_id CASCADE")
            )
            connection.execute(
                text("DELETE FROM permissions WHERE name = 'webhooks:test'")
            )
            connection.execute(
                text("UPDATE alembic_version SET version_num = :stamp"),
                {"stamp": legacy_stamp},
            )

        _run_alembic(backend_dir, isolated_url, "upgrade", "head")
        _run_alembic(backend_dir, isolated_url, "upgrade", "head")

        with schema_engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema()"
                    )
                ).scalars()
            )
            permission_count = connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE name = 'webhooks:test'")
            ).scalar_one()
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert "tenants" in tables
        assert "vendors" in tables
        assert "purchase_orders" in tables
        assert permission_count == 1
        assert version == "010"
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_stripe_idempotency_migration_survives_downgrade_and_reupgrade() -> None:
    """Retained Stripe safety objects must not break a later upgrade."""
    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        pytest.skip("DATABASE_URL is not configured")
    base_url = make_url(raw_url)
    if base_url.get_backend_name() != "postgresql":
        pytest.skip("Migration downgrade regression requires PostgreSQL")
    base_url = base_url.set(drivername="postgresql+psycopg2")

    backend_dir = Path(__file__).resolve().parents[2]
    schema = f"stripe_reupgrade_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(base_url)
    schema_engine = None

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        query = dict(base_url.query)
        query["options"] = f"-csearch_path={schema}"
        isolated_url = base_url.set(query=query).render_as_string(hide_password=False)
        schema_engine = create_engine(isolated_url)

        _run_alembic(backend_dir, isolated_url, "upgrade", "head")
        _run_alembic(backend_dir, isolated_url, "downgrade", "008")
        _run_alembic(backend_dir, isolated_url, "upgrade", "head")
        _run_alembic(backend_dir, isolated_url, "upgrade", "head")

        with schema_engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema()"
                    )
                ).scalars()
            )
            indexes = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema()"
                    )
                )
            }
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert "stripe_webhook_events" in tables
        assert "uq_payments_stripe_payment_intent_id" in indexes
        assert "ix_stripe_webhook_events_processed_at" in indexes
        assert version == "010"
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
