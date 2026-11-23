import pytest

from app.database import normalize_database_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgres://user:password@db:5432/erp",
            "postgresql+psycopg2://user:password@db:5432/erp",
        ),
        (
            "postgresql://user:password@db:5432/erp",
            "postgresql+psycopg2://user:password@db:5432/erp",
        ),
        (
            "postgresql+psycopg2://user:password@db:5432/erp",
            "postgresql+psycopg2://user:password@db:5432/erp",
        ),
        ("sqlite:///./test.db", "sqlite:///./test.db"),
    ],
)
def test_database_url_selects_installed_postgresql_driver(
    source: str, expected: str
) -> None:
    assert normalize_database_url(source) == expected
