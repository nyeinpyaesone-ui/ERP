"""Tests for selecting the configured PostgreSQL DBAPI driver."""

from app.database import normalize_database_url


def test_normalizes_driverless_postgresql_url() -> None:
    assert normalize_database_url("postgresql://user:pass@db:5432/erp") == (
        "postgresql+psycopg2://user:pass@db:5432/erp"
    )


def test_normalizes_legacy_postgres_url() -> None:
    assert normalize_database_url("postgres://user:pass@db:5432/erp") == (
        "postgresql+psycopg2://user:pass@db:5432/erp"
    )


def test_preserves_explicit_postgresql_driver() -> None:
    url = "postgresql+psycopg://user:pass@db:5432/erp"
    assert normalize_database_url(url) == url


def test_preserves_sqlite_url() -> None:
    url = "sqlite:///./test.db"
    assert normalize_database_url(url) == url
