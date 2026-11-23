import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models_stripe import StripeWebhookEvent
from app.routers import integrations, payments

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "status,expected",
    [(200, "delivered"), (204, "delivered"), (302, "failed"), (400, "failed"), (500, "failed")],
)
def test_webhook_delivery_uses_allowlist_and_records_result(
    db: Mock,
    actor: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected: str,
) -> None:
    monkeypatch.setattr(integrations.settings, "WEBHOOK_ALLOWED_HOSTS", "hooks.example.com")
    monkeypatch.setattr(
        integrations.socket,
        "getaddrinfo",
        Mock(return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]),
    )
    webhook = SimpleNamespace(
        id=7,
        url="https://hooks.example.com/hook",
        secret="synthetic-secret",
        is_active=True,
        last_triggered=None,
    )
    db.query.return_value.first.return_value = webhook
    response = SimpleNamespace(status_code=status, text="accepted")
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(integrations.httpx, "Client", client_factory)

    delivery = integrations.test_webhook(7, db, actor)

    assert delivery.status == expected
    assert delivery.response_status == status
    assert delivery.response_body == "accepted"
    request = client.post.call_args
    assert request.args == ("https://hooks.example.com/hook",)
    expected_signature = hmac.new(
        b"synthetic-secret", request.kwargs["content"], hashlib.sha256
    ).hexdigest()
    assert request.kwargs["headers"]["X-Webhook-Signature"] == f"sha256={expected_signature}"
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    assert client_factory.call_args.kwargs["trust_env"] is False
    assert db.add.call_count == 1
    assert db.commit.call_count == 2
    assert webhook.last_triggered is not None


def test_webhook_destination_rejects_private_and_non_allowlisted_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(integrations.settings, "WEBHOOK_ALLOWED_HOSTS", "hooks.example.com")
    with pytest.raises(HTTPException) as error:
        integrations._validate_webhook_url("http://127.0.0.1/admin")
    assert error.value.status_code == 422

    with pytest.raises(HTTPException) as error:
        integrations._validate_webhook_url("https://other.example.com/hook")
    assert error.value.status_code == 422


def test_webhook_destination_rejects_private_dns_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(integrations.settings, "WEBHOOK_ALLOWED_HOSTS", "hooks.example.com")
    monkeypatch.setattr(
        integrations.socket,
        "getaddrinfo",
        Mock(return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]),
    )
    with pytest.raises(HTTPException) as error:
        integrations._validate_webhook_url("https://hooks.example.com/hook", resolve=True)
    assert error.value.status_code == 422


def test_webhook_public_response_never_serializes_secret() -> None:
    webhook = SimpleNamespace(
        id=1,
        name="ERP hook",
        url="https://hooks.example.com/erp",
        events=["invoice.created"],
        is_active=True,
        retry_count=3,
        last_triggered=None,
        created_by=42,
        created_at=None,
        secret="must-not-leak",
    )
    response = integrations.WebhookPublic.model_validate(webhook)
    assert "secret" not in response.model_dump()


def test_disable_webhook_preserves_record_and_history(
    db: Mock, actor: SimpleNamespace
) -> None:
    webhook = SimpleNamespace(id=7, is_active=True)
    db.query.return_value.first.return_value = webhook

    response = integrations.disable_webhook(7, db, actor)

    assert response == {"status": "disabled", "webhook_id": 7}
    assert webhook.is_active is False
    db.delete.assert_not_called()
    db.commit.assert_called_once_with()


def test_unknown_webhook_returns_404_on_disable(db: Mock, actor: SimpleNamespace) -> None:
    db.query.return_value.first.return_value = None
    with pytest.raises(HTTPException) as error:
        integrations.disable_webhook(999, db, actor)
    assert error.value.status_code == 404


def test_stripe_webhook_processing_is_idempotent(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payments, "SessionLocal", Mock(return_value=db))
    invoice = SimpleNamespace(id=7, total=100, amount_paid=75, status="partial")
    db.query.return_value.first.side_effect = [None, invoice, None]
    event = {
        "id": "evt_test_1",
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

    assert payments._process_stripe_event(event) == "processed"

    added = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(added[0], StripeWebhookEvent)
    assert added[0].event_id == "evt_test_1"
    payment = added[1]
    assert (
        payment.invoice_id,
        payment.amount,
        payment.stripe_payment_intent_id,
        payment.stripe_charge_id,
    ) == (7, 25, "pi_test", "ch_test")
    assert payment.status == "completed"
    assert (invoice.amount_paid, invoice.status) == (100, "paid")
    db.commit.assert_called_once_with()
    db.close.assert_called_once_with()


def test_duplicate_stripe_event_has_no_side_effects(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payments, "SessionLocal", Mock(return_value=db))
    db.query.return_value.first.return_value = StripeWebhookEvent(
        event_id="evt_duplicate", event_type="payment_intent.succeeded"
    )
    event = {"id": "evt_duplicate", "type": "payment_intent.succeeded", "data": {"object": {}}}

    assert payments._process_stripe_event(event) == "duplicate"
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once_with()


def test_distinct_stripe_events_for_same_intent_do_not_double_pay(
    db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payments, "SessionLocal", Mock(return_value=db))
    invoice = SimpleNamespace(id=7, total=100, amount_paid=25, status="partial")
    existing_payment = SimpleNamespace(stripe_payment_intent_id="pi_existing")
    db.query.return_value.first.side_effect = [None, invoice, existing_payment]
    event = {
        "id": "evt_second_delivery",
        "type": "payment_intent.succeeded",
        "data": {"object": {
            "id": "pi_existing",
            "metadata": {"invoice_id": "7"},
            "amount_received": 2500,
        }},
    }

    assert payments._process_stripe_event(event) == "processed"
    assert isinstance(db.add.call_args.args[0], StripeWebhookEvent)
    assert db.add.call_count == 1
    assert invoice.amount_paid == 25
    db.commit.assert_called_once_with()
