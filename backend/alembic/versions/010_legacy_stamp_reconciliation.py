"""Reconcile legacy tenancy and permission schemas on later revision stamps.

Revision ID: 010
Revises: 009

Some deployed databases recorded revisions 006–008 before the duplicate-005
compatibility repair was introduced. Those databases skip the earlier repair
migrations when upgrading. Re-run the additive, idempotent repairs at the
current head so these installations converge without dropping existing data.
"""

import runpy
from collections.abc import Sequence
from pathlib import Path

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    versions = Path(__file__).resolve().parent
    tenancy = runpy.run_path(str(versions / "005_add_tenancy_support.py"))
    permissions = runpy.run_path(str(versions / "005_permissions_reconcile_compat.py"))
    tenancy["upgrade"]()
    permissions["upgrade"]()


def downgrade() -> None:
    # These repairs are additive and intentionally preserve existing ERP data.
    pass
