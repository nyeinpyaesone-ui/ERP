"""Add created_by audit column to payments

app/routers/finance.py (create_payment) and the finance unit tests have long
written Payment(created_by=user.id), but the column was missing from both the
ORM model and migration 001_initial — every payment POST failed with a
TypeError at runtime. This migration closes that drift.

Revision ID: 005
Revises: 004
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode: SQLite cannot ALTER constraints directly; batch_alter_table
    # uses the copy-and-move strategy there and is a no-op wrapper on
    # PostgreSQL, so this migration applies cleanly to every supported dialect.
    with op.batch_alter_table('payments') as batch_op:
        batch_op.add_column(
            sa.Column('created_by', sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            'fk_payments_created_by_users',
            'users',
            ['created_by'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_constraint('fk_payments_created_by_users', type_='foreignkey')
        batch_op.drop_column('created_by')
