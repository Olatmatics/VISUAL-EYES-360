import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_request_meta, write_audit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_hash,
    verify_password,
)
from app.db.base import get_db
from app.models.auth import (
    LoginSession,
    PasswordResetToken,
    RefreshToken,
    Role,
    User,
    utcnow,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SetupAdminRequest,
    UserContext,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


def _user_context(user: User) -> UserContext:
    return UserContext(
        id=user.id,
        user_id=user.user_id,
        full_name=user.full_name,
        role=user.role.code if user.role else "UNKNOWN",
        is_super_admin=user.is_super_admin,
        permissions=sorted(user.permission_keys()),
        stations=[station.id for station in user.stations],
        all_stations=user.all_stations,
        must_change_password=user.must_change_password,
    )


def _issue_tokens(db: Session, user: User, request: Request | None = None) -> dict[str, Any]:
    access = create_access_token(user.id, {"role": user.role.code if user.role else "UNKNOWN"})
    refresh = create_refresh_token(user.id, str(uuid.uuid4()))
    access_payload = decode_token(access)
    refresh_payload = decode_token(refresh)

    ip, user_agent = get_request_meta(request) if request else (None, None)
    db.add(
        LoginSession(
            user_id=user.id,
            jti=access_payload["jti"],
            ip=ip,
            user_agent=user_agent,
            expires_at=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash(refresh),
            family_id=refresh_payload["family_id"],
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _user_context(user).model_dump(),
    }


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    exists = db.scalar(
        select(User).where(User.role.has(Role.code == "SUPERIOR_ADMIN"))
    )
    return {"setup_required": exists is None}


@router.post("/setup/admin", status_code=status.HTTP_201_CREATED)
def setup_admin(payload: SetupAdminRequest, request: Request, db: Session = Depends(get_db)):
    if payload.setup_token != settings.SETUP_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid setup token")

    exists = db.scalar(select(User).where(User.role.has(Role.code == "SUPERIOR_ADMIN")))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Initial setup already completed")

    if db.scalar(select(User).where(func.lower(User.user_id) == payload.user_id.lower())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User ID already exists")

    role = db.scalar(select(Role).where(Role.code == "SUPERIOR_ADMIN"))
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role catalogue missing")

    admin = User(
        user_id=payload.user_id,
        full_name=payload.full_name,
        role_id=role.id,
        phone=payload.phone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_super_admin=True,
        is_active=True,
        all_stations=True,
        recovery_info=payload.recovery_info,
    )
    db.add(admin)
    db.flush()
    write_audit(db, admin, "SETUP_SUPERIOR_ADMIN", "User", admin.id, request=request)
    db.commit()
    return {"message": "Superior Administrator created", "user_id": admin.user_id}


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.user_id) == payload.user_id.lower()))
    generic = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user is None:
        raise generic
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    if user.locked_until and user.locked_until > utcnow():
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked")

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        db.commit()
        raise generic

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    db.flush()
    write_audit(db, user, "LOGIN", "User", user.id, request=request)
    return _issue_tokens(db, user, request)


@router.post("/auth/refresh")
async def refresh(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    refresh_token = body.get("refresh_token") if isinstance(body, dict) else None
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="refresh_token required")
    try:
        claims = decode_token(refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(refresh_token)))
    if record is None or record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    if record.used_at is not None:
        db.execute(
            update(RefreshToken).where(RefreshToken.family_id == record.family_id).values(revoked_at=utcnow())
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected")
    if record.expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.scalar(select(User).where(User.id == claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")

    record.used_at = utcnow()
    db.flush()
    access = create_access_token(user.id, {"role": user.role.code if user.role else "UNKNOWN"})
    new_refresh = create_refresh_token(user.id, record.family_id)
    access_payload = decode_token(access)
    refresh_payload = decode_token(new_refresh)
    db.add(
        LoginSession(
            user_id=user.id,
            jti=access_payload["jti"],
            expires_at=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash(new_refresh),
            family_id=refresh_payload["family_id"],
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _user_context(user).model_dump(),
    }


@router.post("/auth/logout")
def logout(
    request: Request,
    payload: dict[str, Any] | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.split(" ", 1)[1] if " " in auth_header else ""
    claims = {}
    if token:
        try:
            claims = decode_token(token)
        except Exception:
            claims = {}
    if claims.get("jti"):
        db.execute(
            update(LoginSession).where(LoginSession.jti == claims["jti"]).values(revoked_at=utcnow())
        )
    if payload and payload.get("refresh_token"):
        try:
            refresh_claims = decode_token(payload["refresh_token"])
            db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == refresh_claims.get("family_id"))
                .values(revoked_at=utcnow())
            )
        except Exception:
            pass
    db.flush()
    write_audit(db, user, "LOGOUT", "User", user.id, request=request)
    db.commit()
    return {"message": "Logged out"}


@router.get("/auth/me", response_model=UserContext)
def me(user: User = Depends(get_current_user)):
    return _user_context(user)


@router.post("/auth/password/change")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.flush()
    write_audit(db, user, "CHANGE_PASSWORD", "User", user.id, request=request)
    db.commit()
    return {"message": "Password changed"}


@router.post("/auth/password/forgot")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.user_id) == payload.user_id.lower()))
    if user is None:
        return {"message": "If the account exists, a reset link has been issued"}
    raw = str(uuid.uuid4()) + str(uuid.uuid4())
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    db.commit()
    response: dict[str, Any] = {"message": "If the account exists, a reset link has been issued"}
    if settings.ENVIRONMENT == "development":
        response["dev_token"] = raw
    return response


@router.post("/auth/password/reset")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(payload.token))
    )
    if record is None or record.used_at is not None or record.expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    user = db.scalar(select(User).where(User.id == record.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    user.password_hash = hash_password(payload.new_password)
    user.failed_attempts = 0
    user.locked_until = None
    record.used_at = utcnow()
    db.flush()
    write_audit(db, user, "RESET_PASSWORD", "User", user.id)
    db.commit()
    return {"message": "Password reset"}
