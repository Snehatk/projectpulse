"""FastAPI dependencies for JWT authentication and Role-Based Access Control (RBAC)."""

import json
from datetime import datetime
import logging
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_access_token, hash_device_token
from backend.database import get_db
from backend.models.db_models import AuditLogRecord, DeviceToken, User
from shared.timeutil import utc_now_naive

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


def log_audit_event(
    db: Session,
    user_id: str,
    action: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record a security-relevant event to the audit log."""
    try:
        record = AuditLogRecord(
            user_id=user_id,
            action=action,
            details_json=json.dumps(details or {}),
            ip_address=ip_address,
            timestamp=utc_now_naive(),
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        logger.error("Failed to record audit log: %s", exc)
        db.rollback()


def get_current_user(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the currently logged-in user from the JWT token."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
        )

    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your Project Manager.",
        )

    return user


def get_current_active_user_optional(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Optional user resolution for endpoints that support public or authenticated views."""
    if not auth or not auth.credentials:
        return None
    payload = decode_access_token(auth.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_role(allowed_roles: list[str]) -> Callable:
    """Factory creating a FastAPI dependency enforcing that the user has one of allowed_roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.upper()
        allowed_upper = [r.upper() for r in allowed_roles]
        if user_role not in allowed_upper:
            logger.warning(
                "Access denied for user %s (role: %s) on endpoint requiring %s",
                current_user.user_id,
                user_role,
                allowed_upper,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{user_role}' does not have permission for this resource.",
            )
        return current_user

    return role_checker


def get_authenticated_agent_device(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> DeviceToken:
    """Validate desktop agent device token and verify it is not revoked."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent device authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = auth.credentials
    token_h = hash_device_token(raw_token)
    device = db.query(DeviceToken).filter(DeviceToken.token_hash == token_h).first()

    if not device:
        # Check if it was signed as a JWT (fallback during pairing/testing)
        payload = decode_access_token(raw_token)
        if payload and payload.get("device_id"):
            device = db.query(DeviceToken).filter(DeviceToken.device_id == payload["device_id"]).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unrecognized device token. Please pair this device from the dashboard.",
        )

    if device.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This device has been revoked by the Project Manager.",
        )

    # Update last seen timestamp
    device.last_used_at = utc_now_naive()
    db.commit()

    return device
