from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import AccessLog


def log_access(
    db: Session,
    action: str,
    success: bool,
    user_id: int | None = None,
    document_id: int | None = None,
    reason: str | None = None,
    request: Request | None = None,
):
    ip = None
    if request:
        ip = request.client.host if request.client else None

    entry = AccessLog(
        user_id=user_id,
        action=action,
        document_id=document_id,
        success=success,
        reason=reason,
        ip=ip,
    )
    db.add(entry)
    db.commit()
