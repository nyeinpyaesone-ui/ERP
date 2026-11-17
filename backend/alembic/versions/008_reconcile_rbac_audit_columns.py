"""Reconcile RBAC, LLM and audit columns with app.models

Revision ID: 008
Revises: 007
Create Date: 2026-10-03

- ``user_roles``: add ``assigned_by`` / ``created_at`` (declared on the model
  since 002, never created in the database).
- ``role_permissions``: add ``created_at`` (same story).
- ``roles``, ``llm_models``, ``ai_prompt_templates``, ``data_policies``,
  ``field_permissions``: add ``updated_at``. The model sets
  ``server_default=now()`` plus a Python-side ``onupdate``; no migration ever
  added the column, so every ``SELECT`` of these tables failed on a migrated
  database.
- ``ai_conversations``: drop ``context``; ``ai_messages``: drop
  ``tool_calls``. 003 created both, the ORM models never declared them and
  nothing reads them (the ``tool_calls`` in ``llm_service`` is a dict from the
  Ollama payload, not a column).

After 007 + 008 the migrated schema agrees with ``Base.metadata``
table-for-table. The join tables keep their composite primary keys from 002 —
they are what actually prevents duplicate role grants — so the ORM models were
changed to match rather than the other way round.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables the model declares ``updated_at`` on but no migration ever created.
_UPDATED_AT_TABLES = (
    "roles",
    "llm_models",
    "ai_prompt_templates",
    "data_policies",
    "field_permissions",
)


def upgrade() -> None:
    # ── RBAC junction tables ───────────────────────────────────────────────
    op.add_column(
        "user_roles",
        sa.Column("assigned_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_roles_assigned_by_users",
        "user_roles",
        "users",
        ["assigned_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "user_roles",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "role_permissions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # ── updated_at missing on five tables ──────────────────────────────────
    for table in _UPDATED_AT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            ),
        )

    # ── columns the ORM models never declared ──────────────────────────────
    op.drop_column("ai_conversations", "context")
    op.drop_column("ai_messages", "tool_calls")


def downgrade() -> None:
    op.add_column(
        "ai_messages",
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "ai_conversations",
        sa.Column("context", postgresql.JSONB(), nullable=True),
    )

    for table in reversed(_UPDATED_AT_TABLES):
        op.drop_column(table, "updated_at")

    op.drop_column("role_permissions", "created_at")
    op.drop_column("user_roles", "created_at")
    op.drop_constraint(
        "fk_user_roles_assigned_by_users", "user_roles", type_="foreignkey"
    )
    op.drop_column("user_roles", "assigned_by")
