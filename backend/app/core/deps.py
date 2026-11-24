from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

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
    """Station ids this user may touch.

    ``None`` means national (unrestricted) access. Otherwise the result is the
    union of explicitly assigned stations and every station inside the user's
    geographic scope (state or LGA).
    """
    if user.is_super_admin or user.all_stations:
        return None

    ids = {station.id for station in user.stations}
    if user.scope_state_id or user.scope_lga_id:
        session = object_session(user)
        if session is not None:
            from app.models.core import Station

            query = select(Station.id)
            if user.scope_lga_id:
                query = query.where(Station.lga_id == user.scope_lga_id)
            elif user.scope_state_id:
                query = query.where(Station.state_id == user.scope_state_id)
            ids |= set(session.scalars(query).all())
    return sorted(ids)


def allowed_state_ids(user: User) -> list[str] | None:
    """State ids visible to the user. ``None`` means national access."""
    if user.is_super_admin or user.all_stations:
        return None
    if user.scope_state_id and not user.scope_lga_id:
        return [user.scope_state_id]
    session = object_session(user)
    station_ids = allowed_station_ids(user) or []
    if session is None:
        return []
    from app.models.core import Station

    if not station_ids:
        return []
    return sorted(
        {
            row
            for row in session.scalars(
                select(Station.state_id).where(Station.id.in_(station_ids), Station.state_id.is_not(None))
            ).all()
            if row
        }
    )


def scoped_station_or_404(db: Session, user: User, station_id: str):
    from app.models.core import Station

    station = db.scalar(select(Station).where(Station.id == station_id))
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    allowed = allowed_station_ids(user)
    if allowed is not None and station.id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Station access denied")
    return station


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
