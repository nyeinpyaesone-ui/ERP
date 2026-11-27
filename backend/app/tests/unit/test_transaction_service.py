"""Unit tests for transaction and compensation helpers."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.services.transaction_service import CompensationTransaction, TransactionService


@asynccontextmanager
async def _transaction_scope():
    yield


class FakeAsyncSession:
    def __init__(self, scopes=None):
        self.begin = Mock(side_effect=scopes or [_transaction_scope()])
        self.rollback = AsyncMock()
        self.add = Mock()
        self.flush = AsyncMock()


def _deadlock_error():
    return OperationalError("UPDATE accounts", {}, Exception("deadlock detected"))


async def test_transaction_yields_session_on_success():
    db = FakeAsyncSession()

    async with TransactionService.transaction(db) as session:
        assert session is db

    db.rollback.assert_not_awaited()


@pytest.mark.parametrize(
    "error", [SQLAlchemyError("database error"), ValueError("invalid")]
)
async def test_transaction_rolls_back_and_reraises(error):
    db = FakeAsyncSession()

    with pytest.raises(type(error)):
        async with TransactionService.transaction(db):
            raise error

    db.rollback.assert_awaited_once()


async def test_execute_atomic_returns_results_in_operation_order():
    db = FakeAsyncSession()

    async def first(_db):
        return "first"

    async def second(_db):
        return "second"

    assert await TransactionService.execute_atomic(db, [first, second]) == [
        "first",
        "second",
    ]


async def test_execute_atomic_rolls_back_when_operation_fails():
    db = FakeAsyncSession()

    async def fail(_db):
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        await TransactionService.execute_atomic(db, [fail])

    db.rollback.assert_awaited_once()


async def test_retry_on_deadlock_retries_then_returns_result():
    db = FakeAsyncSession([_transaction_scope(), _transaction_scope()])
    operation = AsyncMock(side_effect=[_deadlock_error(), "committed"])

    result = await TransactionService.retry_on_deadlock(db, operation, max_retries=2)

    assert result == "committed"
    assert operation.await_count == 2
    db.rollback.assert_awaited_once()


async def test_retry_on_deadlock_does_not_retry_other_operational_errors():
    db = FakeAsyncSession([_transaction_scope(), _transaction_scope()])
    error = OperationalError("SELECT 1", {}, Exception("connection lost"))
    operation = AsyncMock(side_effect=error)

    with pytest.raises(OperationalError):
        await TransactionService.retry_on_deadlock(db, operation, max_retries=2)

    operation.assert_awaited_once()
    db.rollback.assert_not_awaited()


async def test_retry_on_deadlock_reraises_after_last_attempt():
    db = FakeAsyncSession([_transaction_scope(), _transaction_scope()])
    error = _deadlock_error()
    operation = AsyncMock(side_effect=error)

    with pytest.raises(OperationalError):
        await TransactionService.retry_on_deadlock(db, operation, max_retries=2)

    assert operation.await_count == 2
    db.rollback.assert_awaited_once()


async def test_log_transaction_persists_audit_record(monkeypatch):
    db = FakeAsyncSession()
    monkeypatch.setattr(
        "app.services.transaction_service.TransactionLog",
        lambda **values: SimpleNamespace(**values),
    )

    transaction_id = await TransactionService.log_transaction(
        db,
        entity_type="invoice",
        entity_id=42,
        action="paid",
        old_values={"status": "open"},
        new_values={"status": "paid"},
        user_id=7,
        tenant_id=3,
    )

    record = db.add.call_args.args[0]
    assert transaction_id.startswith("invoice_42_")
    assert record.transaction_id == transaction_id
    assert record.old_values == {"status": "open"}
    assert record.new_values == {"status": "paid"}
    assert record.user_id == 7
    assert record.tenant_id == 3
    db.flush.assert_awaited_once()


async def test_compensation_rollback_runs_in_reverse_order():
    transaction = CompensationTransaction(FakeAsyncSession())
    events = []

    async def operation(name):
        events.append(f"operation:{name}")

    async def compensation(name):
        events.append(f"compensation:{name}")

    await transaction.add_operation(
        lambda: operation("one"), lambda: compensation("one")
    )
    await transaction.add_operation(
        lambda: operation("two"), lambda: compensation("two")
    )
    await transaction.rollback()

    assert events == [
        "operation:one",
        "operation:two",
        "compensation:two",
        "compensation:one",
    ]


async def test_compensation_failure_does_not_stop_remaining_rollbacks():
    transaction = CompensationTransaction(FakeAsyncSession())
    events = []

    async def failing_compensation():
        events.append("failed")
        raise RuntimeError("compensation unavailable")

    async def successful_compensation():
        events.append("succeeded")

    transaction.compensations = [successful_compensation, failing_compensation]
    await transaction.rollback()

    assert events == ["failed", "succeeded"]


async def test_failed_operation_triggers_prior_compensation():
    transaction = CompensationTransaction(FakeAsyncSession())
    events = []

    async def successful_operation():
        events.append("operation")

    async def compensate():
        events.append("compensated")

    async def failing_operation():
        raise RuntimeError("operation failed")

    await transaction.add_operation(successful_operation, compensate)

    with pytest.raises(RuntimeError, match="operation failed"):
        await transaction.add_operation(failing_operation, compensate)

    assert events == ["operation", "compensated"]
