import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.routers import integrations, payments

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "status,expected",
    [(200, "delivered"), (399, "delivered"), (400, "failed"), (500, "failed")],
)
async def test_webhook_delivery_persists_result_and_signature(
    db: Mock,
    actor: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected: str,
) -> None:
    db.query.return_value.first.return_value = SimpleNamespace(
        url="https://example.invalid/hook", secret="synthetic-secret"
    )
    client = AsyncMock()
    client.post.return_value = SimpleNamespace(status_code=status, text="x" * 1001)
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(integrations.httpx, "AsyncClient", Mock(return_value=context))

    delivery = await integrations.test_webhook(7, db, actor)

    assert delivery.status == expected
    assert delivery.response_status == status
    assert len(delivery.response_body) == 1000
    assert (delivery.webhook_id, delivery.event, delivery.attempt) == (7, "test", 1)
    request = client.post.await_args
    assert request.args == ("https://example.invalid/hook",)
    expected_signature = hmac.new(
        b"synthetic-secret", json.dumps(request.kwargs["json"]).encode(), hashlib.sha256
    ).hexdigest()
    assert (
        request.kwargs["headers"]["X-Webhook-Signature"]
        == f"sha256={expected_signature}"
    )
    db.add.assert_called_once_with(delivery)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(delivery)


async def test_webhook_network_failure_is_recorded(
    db: Mock, actor: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    db.query.return_value.first.return_value = SimpleNamespace(
        url="https://example.invalid/hook", secret=None
    )
    client = AsyncMock()
    client.post.side_effect = RuntimeError("network unavailable")
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(integrations.httpx, "AsyncClient", Mock(return_value=context))
    delivery = await integrations.test_webhook(7, db, actor)
    assert (delivery.status, delivery.response_body) == (
        "failed",
        "network unavailable",
    )
    assert "X-Webhook-Signature" not in client.post.await_args.kwargs["headers"]
    db.commit.assert_called_once_with()


async def test_unknown_webhook_does_not_send_request(
    db: Mock, actor: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Mock()
    monkeypatch.setattr(integrations.httpx, "AsyncClient", client)
    with pytest.raises(HTTPException) as error:
        await integrations.test_webhook(999, db, actor)
    assert error.value.status_code == 404
    client.assert_not_called()
    db.add.assert_not_called()


async def test_stripe_webhook_persists_payment_after_async_database_calls(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payments.settings, "STRIPE_WEBHOOK_SECRET", "synthetic-secret")
    event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test",
                "metadata": {"invoice_id": "7"},
                "amount_received": 2500,
                "charges": {"data": [{"id": "ch_test"}]},
            }
        },
    }
    monkeypatch.setattr(
        payments.stripe.Webhook, "construct_event", Mock(return_value=event)
    )
    invoice = SimpleNamespace(id=7, total=100, amount_paid=75, status="partial")
    db.query.return_value.first.return_value = invoice
    request = SimpleNamespace(
        body=AsyncMock(return_value=b"synthetic-payload"),
        headers={"stripe-signature": "synthetic-signature"},
    )

    assert await payments.stripe_webhook(request, db) == {"status": "success"}

    payment = db.add.call_args.args[0]
    assert (
        payment.invoice_id,
        payment.amount,
        payment.stripe_payment_intent_id,
        payment.stripe_charge_id,
    ) == (7, 25, "pi_test", "ch_test")
    assert payment.status == "completed"
    assert (invoice.amount_paid, invoice.status) == (100, "paid")
    db.commit.assert_called_once_with()
