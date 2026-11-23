from collections.abc import Callable, Generator
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.base import get_db
from app.models.auth import AuditLog, LoginSession, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

PASSWORD_CHANGE_ALLOWED_PATHS = {
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
    "/api/v1/auth/password/change",
}


def get_request_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    return ip, request.headers.get("user-agent")


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_token(token)
    except Exception:
        raise credentials_error
    if payload.get("type") != "access" or not payload.get("sub"):
        raise credentials_error

    user = db.scalar(select(User).where(User.id == payload["sub"]))
    if user is None or not user.is_active:
        raise credentials_error

    session = db.scalar(select(LoginSession).where(LoginSession.jti == payload.get("jti")))
    if session is None or session.revoked_at is not None:
        raise credentials_error

    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )

    return user


def require_permission(module: str, action: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(module, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superior Administrator access required")
    return user


def allowed_station_ids(user: User) -> list[str] | None:
    if user.is_super_admin or user.all_stations:
        return None
    return [station.id for station in user.stations]


def write_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    import json

    ip = user_agent = None
    if request is not None:
        ip, user_agent = get_request_meta(request)
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_user_id=actor.user_id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=json.dumps(before, default=str) if before is not None else None,
        after_json=json.dumps(after, default=str) if after is not None else None,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry
