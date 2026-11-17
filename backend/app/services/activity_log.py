from typing import Any

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log_activity(
    db: Session,
    user_id: int | None = None,
    action: str = "",
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """Log an activity to the database."""
    log = ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    db.commit()
    return log
