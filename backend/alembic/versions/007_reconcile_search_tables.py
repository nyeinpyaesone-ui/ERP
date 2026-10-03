"""Reconcile search tables with app.models

Revision ID: 007
Revises: 006
Create Date: 2026-10-03

Migration 004 created a schema that never matched the ORM models, so every
`/api/v1/search/*` call failed on a migrated database:

- 004 created ``search_indexes``; ``SearchIndex.__tablename__`` is
  ``search_index``.
- ``SearchIndex`` needs ``metadata`` (present), ``embedding`` (missing) and
  ``updated_at`` (present) but not ``tags``/``searchable_text``.
- ``SearchQuery`` in the model uses ``entity_types``; 004 used ``filters`` and
  ``clicked_results``, and had no FK to ``users``.
- ``SearchSuggestion`` in the model uses ``query``/``count``; 004 used
  ``query_text``/``frequency`` and added a unique constraint the model does not
  declare, while omitting ``created_at``.

Hand-written: ``alembic revision --autogenerate`` is only now safe to use
(007 pairs with the ``import app.models`` fix in ``alembic/env.py``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── search_index ────────────────────────────────────────────────────────
    op.drop_index("ix_search_indexes_searchable_text", table_name="search_indexes")
    op.drop_index("ix_search_indexes_entity_type", table_name="search_indexes")
    op.rename_table("search_indexes", "search_index")

    op.drop_column("search_index", "searchable_text")
    op.drop_column("search_index", "tags")
    op.add_column(
        "search_index", sa.Column("embedding", sa.LargeBinary(), nullable=True)
    )
    op.alter_column(
        "search_index",
        "title",
        existing_type=sa.String(length=500),
        nullable=False,
    )
    op.create_index("ix_search_index_id", "search_index", ["id"], unique=False)
    op.create_index(
        "ix_search_index_entity_type", "search_index", ["entity_type"], unique=False
    )
    op.create_index(
        "ix_search_index_entity_id", "search_index", ["entity_id"], unique=False
    )
    op.create_index(
        "ix_search_index_created_at", "search_index", ["created_at"], unique=False
    )

    # ── search_queries ──────────────────────────────────────────────────────
    op.drop_column("search_queries", "filters")
    op.drop_column("search_queries", "clicked_results")
    op.add_column(
        "search_queries",
        sa.Column("entity_types", postgresql.JSONB(), nullable=True),
    )
    op.alter_column(
        "search_queries",
        "query",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
    op.create_foreign_key(
        "fk_search_queries_user_id",
        "search_queries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── search_suggestions ──────────────────────────────────────────────────
    op.drop_constraint("uq_search_suggestion", "search_suggestions", "unique")
    op.alter_column(
        "search_suggestions",
        "query_text",
        existing_type=sa.String(length=255),
        type_=sa.String(length=500),
        new_column_name="query",
    )
    op.alter_column(
        "search_suggestions",
        "frequency",
        existing_type=sa.Integer(),
        new_column_name="count",
    )
    op.alter_column(
        "search_suggestions",
        "entity_type",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.drop_column("search_suggestions", "suggestion_type")
    op.drop_column("search_suggestions", "entity_id")
    op.add_column(
        "search_suggestions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_search_suggestions_id", "search_suggestions", ["id"], unique=False
    )
    op.create_index(
        "ix_search_suggestions_query", "search_suggestions", ["query"], unique=False
    )
    op.create_index(
        "ix_search_suggestions_entity_type",
        "search_suggestions",
        ["entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_search_suggestions_entity_type", table_name="search_suggestions")
    op.drop_index("ix_search_suggestions_query", table_name="search_suggestions")
    op.drop_index("ix_search_suggestions_id", table_name="search_suggestions")
    op.drop_column("search_suggestions", "created_at")
    op.add_column(
        "search_suggestions",
        sa.Column("entity_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_suggestions",
        sa.Column(
            "suggestion_type",
            sa.String(length=50),
            nullable=False,
            server_default="autocomplete",
        ),
    )
    op.alter_column(
        "search_suggestions",
        "entity_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "search_suggestions",
        "count",
        existing_type=sa.Integer(),
        new_column_name="frequency",
    )
    op.alter_column(
        "search_suggestions",
        "query",
        existing_type=sa.String(length=500),
        type_=sa.String(length=255),
        new_column_name="query_text",
    )
    op.create_unique_constraint(
        "uq_search_suggestion",
        "search_suggestions",
        ["query_text", "suggestion_type", "entity_type"],
    )

    op.drop_constraint("fk_search_queries_user_id", "search_queries", "foreignkey")
    op.alter_column(
        "search_queries",
        "query",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.drop_column("search_queries", "entity_types")
    op.add_column(
        "search_queries",
        sa.Column("clicked_results", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "search_queries", sa.Column("filters", postgresql.JSONB(), nullable=True)
    )

    op.drop_index("ix_search_index_created_at", table_name="search_index")
    op.drop_index("ix_search_index_entity_id", table_name="search_index")
    op.drop_index("ix_search_index_entity_type", table_name="search_index")
    op.drop_index("ix_search_index_id", table_name="search_index")
    op.alter_column(
        "search_index",
        "title",
        existing_type=sa.String(length=500),
        nullable=True,
    )
    op.drop_column("search_index", "embedding")
    op.add_column("search_index", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column(
        "search_index",
        sa.Column(
            "searchable_text", sa.Text(), nullable=False, server_default=sa.text("''")
        ),
    )
    op.rename_table("search_index", "search_indexes")
    op.create_index(
        "ix_search_indexes_entity_type",
        "search_indexes",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_search_indexes_searchable_text",
        "search_indexes",
        ["searchable_text"],
        unique=False,
        postgresql_using="gin",
    )
