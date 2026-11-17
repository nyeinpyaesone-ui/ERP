"""Isolated router/service fixtures; no application startup or external services."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Query, Session


@pytest.fixture
def db() -> Mock:
    session = Mock(spec=Session)
    query = Mock(spec=Query)
    for method in (
        "filter",
        "order_by",
        "offset",
        "limit",
        "with_for_update",
        "group_by",
        "distinct",
        "with_entities",
    ):
        getattr(query, method).return_value = query
    query.first.return_value = None
    query.all.return_value = []
    query.count.return_value = 0
    query.scalar.return_value = None
    session.query.return_value = query
    return session


@pytest.fixture
def actor() -> SimpleNamespace:
    return SimpleNamespace(id=42, role="user", is_active=True, roles=[])


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> Mock:
    from app.routers import auth, crm, documents, finance, hr, inventory

    log = Mock()
    for module in (auth, crm, documents, finance, hr, inventory):
        monkeypatch.setattr(module, "log_activity", log)
    return log
