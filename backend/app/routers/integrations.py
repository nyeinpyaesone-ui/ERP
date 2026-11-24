import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Integration, Webhook, WebhookDelivery
from app.services.permissions import require_permission

router = APIRouter()


class IntegrationCreate(BaseModel):
    name: str
    provider: str
    config: dict[str, Any]


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(max_length=500)
    events: list[str] = Field(min_length=1)
    secret: str | None = Field(default=None, min_length=16, max_length=255)

    @field_validator("url")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        _validate_webhook_url(value)
        return value


class WebhookPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    events: list[str]
    is_active: bool
    retry_count: int
    last_triggered: datetime | None = None
    created_by: int | None = None
    created_at: datetime | None = None


class WebhookDeliveryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    webhook_id: int
    event: str
    payload: dict[str, Any]
    response_status: int | None = None
    response_body: str | None = None
    attempt: int
    status: str
    created_at: datetime | None = None


def _allowed_webhook_hosts() -> set[str]:
    return {
        host.strip().lower().rstrip(".")
        for host in settings.WEBHOOK_ALLOWED_HOSTS.split(",")
        if host.strip()
    }


def _validate_webhook_url(value: str, *, resolve: bool = False) -> str:
    """Fail closed: outbound webhooks require HTTPS and an exact host allowlist."""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid webhook URL") from exc

    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.fragment
    ):
        raise HTTPException(
            status_code=422,
            detail="Webhook URL must be an HTTPS URL on port 443 without embedded credentials",
        )

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(
            status_code=422, detail="IP-literal webhook destinations are not allowed"
        )

    if host not in _allowed_webhook_hosts():
        raise HTTPException(
            status_code=422,
            detail="Webhook destination host is not in WEBHOOK_ALLOWED_HOSTS",
        )

    if resolve:
        _resolve_public_webhook_addresses(host)

    return value


def _resolve_public_webhook_addresses(host: str) -> list[tuple[int, tuple]]:
    """Resolve once, reject mixed/private answers, and return socket addresses.

    The returned sockaddr values are used directly for the connection so the
    HTTP client cannot perform a second DNS lookup after validation.
    """
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HTTPException(
            status_code=422, detail="Webhook destination could not be resolved"
        ) from exc

    if not records or any(
        not ipaddress.ip_address(record[4][0]).is_global for record in records
    ):
        raise HTTPException(
            status_code=422,
            detail="Webhook destination must resolve only to public IP addresses",
        )

    unique = {}
    for family, _socktype, _proto, _canonname, sockaddr in records:
        unique[(family, sockaddr)] = (family, sockaddr)
    return list(unique.values())


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to a validated sockaddr, retaining host SNI."""

    def __init__(self, host: str, family: int, sockaddr: tuple, **kwargs):
        self._address_family = family
        self._validated_sockaddr = sockaddr
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        sock = socket.socket(self._address_family, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self._validated_sockaddr)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _post_webhook_to_pinned_address(
    url: str, family: int, sockaddr: tuple, payload: bytes, headers: dict[str, str]
) -> tuple[int, str]:
    parsed = urlsplit(url)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    connection = _PinnedHTTPSConnection(
        parsed.hostname or "",
        family,
        sockaddr,
        timeout=15.0,
        context=ssl.create_default_context(),
    )
    try:
        connection.request("POST", target, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read(1000).decode("utf-8", errors="replace")
        return response.status, body
    finally:
        connection.close()


@router.post("/integrations")
def create_integration(
    data: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("integrations", "create")),
):
    integration = Integration(**data.model_dump(), created_by=current_user.id)
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.get("/integrations")
def list_integrations(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("integrations", "read")),
):
    return db.query(Integration).all()


@router.post(
    "/webhooks", response_model=WebhookPublic, status_code=status.HTTP_201_CREATED
)
def create_webhook(
    data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("webhooks", "create")),
):
    webhook = Webhook(**data.model_dump(), created_by=current_user.id)
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("/webhooks", response_model=list[WebhookPublic])
def list_webhooks(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("webhooks", "read")),
):
    return db.query(Webhook).order_by(Webhook.created_at.desc()).all()


@router.delete("/webhooks/{webhook_id}")
def disable_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("webhooks", "delete")),
):
    """Disable rather than delete so delivery history and audit references survive."""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook.is_active = False
    db.commit()
    return {"status": "disabled", "webhook_id": webhook_id}


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookDeliveryPublic)
def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("webhooks", "test")),
):
    """Send a guarded test delivery using one synchronous DB session/thread."""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if not webhook.is_active:
        raise HTTPException(status_code=409, detail="Webhook is disabled")

    _validate_webhook_url(webhook.url)
    webhook_host = urlsplit(webhook.url).hostname or ""
    # Resolve once and pin the TCP connection to the validated address.
    # TLS SNI and certificate verification still use the allowlisted hostname.
    pinned_addresses = _resolve_public_webhook_addresses(webhook_host)

    payload = {
        "event": "test",
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {"message": "Test webhook delivery"},
    }
    payload_bytes = json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if webhook.secret:
        signature = hmac.new(
            webhook.secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    delivery = WebhookDelivery(
        webhook_id=webhook_id,
        event="test",
        payload=payload,
        attempt=1,
        status="pending",
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    try:
        family, sockaddr = pinned_addresses[0]
        response_status, response_body = _post_webhook_to_pinned_address(
            webhook.url, family, sockaddr, payload_bytes, headers
        )
        delivery.response_status = response_status
        delivery.response_body = response_body[:1000]
        delivery.status = "delivered" if 200 <= response_status < 300 else "failed"
        webhook.last_triggered = datetime.now(UTC)
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        # Avoid persisting exception strings that can contain sensitive URL data.
        delivery.status = "failed"
        delivery.response_body = f"Request failed: {type(exc).__name__}"

    db.commit()
    db.refresh(delivery)
    return delivery


@router.get(
    "/webhooks/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryPublic],
)
def get_deliveries(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("webhooks", "read")),
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(100)
        .all()
    )
