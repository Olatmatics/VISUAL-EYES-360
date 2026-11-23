from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.catalogue import MODULES
from app.core.deps import require_permission, write_audit
from app.core.security import hash_password
from app.db.base import get_db
from app.models.auth import (
    AccountStatusHistory,
    AuditLog,
    LoginSession,
    Permission,
    Role,
    User,
    UserPermission,
    utcnow,
)
from app.models.core import Station
from app.schemas.user import ManagerCreate, ManagerOut, ManagerUpdate

router = APIRouter(prefix="/api/v1", tags=["users"])


def _out(user: User) -> ManagerOut:
    return ManagerOut(
        id=user.id,
        user_id=user.user_id,
        full_name=user.full_name,
        phone=user.phone,
        email=user.email,
        is_active=user.is_active,
        all_stations=user.all_stations,
        station_ids=[station.id for station in user.stations],
        permissions=sorted(user.permission_keys()),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _get_manager(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Superior Administrator cannot be managed here")
    return user


def _apply_permissions(db: Session, user: User, items) -> None:
    db.query(UserPermission).filter(UserPermission.user_id == user.id).delete()
    for item in items:
        permission = db.scalar(
            select(Permission).where(
                Permission.module_code == item.module, Permission.action_code == item.action
            )
        )
        if permission is None:
            continue
        db.add(
            UserPermission(
                user_id=user.id,
                permission_id=permission.id,
                effect=item.effect if item.effect in ("GRANT", "DENY") else "GRANT",
            )
        )


def _apply_stations(db: Session, user: User, station_ids: list[str]) -> None:
    stations = list(db.scalars(select(Station).where(Station.id.in_(station_ids))).all()) if station_ids else []
    user.stations = stations


@router.get("/users", response_model=list[ManagerOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users", "view")),
):
    users = db.scalars(select(User).where(User.is_super_admin.is_(False))).all()
    return [_out(user) for user in users]


@router.post("/users/managers", response_model=ManagerOut, status_code=status.HTTP_201_CREATED)
def create_manager(
    payload: ManagerCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users", "create")),
):
    if db.scalar(select(User).where(func.lower(User.user_id) == payload.manager_id.lower())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manager ID already exists")
    role = db.scalar(select(Role).where(Role.code == "MANAGER"))
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Manager role missing")

    manager = User(
        user_id=payload.manager_id,
        full_name=payload.full_name,
        role_id=role.id,
        phone=payload.phone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
        all_stations=payload.all_stations,
        must_change_password=True,
    )
    db.add(manager)
    db.flush()
    _apply_permissions(db, manager, payload.permissions)
    _apply_stations(db, manager, payload.station_ids)
    db.flush()
    write_audit(db, actor, "CREATE_MANAGER", "User", manager.id, after=_out(manager).model_dump(), request=request)
    db.commit()
    return _out(manager)


@router.get("/users/{user_id}", response_model=ManagerOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users", "view")),
):
    return _out(_get_manager(db, user_id))


@router.patch("/users/{user_id}", response_model=ManagerOut)
def update_user(
    user_id: str,
    payload: ManagerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users", "edit")),
):
    user = _get_manager(db, user_id)
    before = _out(user).model_dump()
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.email is not None:
        user.email = payload.email
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.all_stations is not None:
        user.all_stations = payload.all_stations
    if payload.permissions is not None:
        _apply_permissions(db, user, payload.permissions)
    if payload.station_ids is not None:
        _apply_stations(db, user, payload.station_ids)
    user.updated_at = utcnow()
    db.flush()
    write_audit(db, actor, "UPDATE_MANAGER", "User", user.id, before=before, after=_out(user).model_dump(), request=request)
    db.commit()
    return _out(user)


@router.post("/users/{user_id}/password/reset")
def reset_manager_password(
    user_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users", "manage")),
):
    user = _get_manager(db, user_id)
    new_password = payload.get("new_password")
    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    db.flush()
    write_audit(db, actor, "RESET_MANAGER_PASSWORD", "User", user.id, request=request)
    db.commit()
    return {"message": "Manager password reset"}


@router.post("/users/{user_id}/status")
def set_user_status(
    user_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users", "manage")),
):
    user = _get_manager(db, user_id)
    is_active = bool(payload.get("is_active"))
    previous = "ACTIVE" if user.is_active else "INACTIVE"
    target = "ACTIVE" if is_active else "INACTIVE"
    user.is_active = is_active
    if not is_active:
        db.execute(
            update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=utcnow())
        )
    db.add(
        AccountStatusHistory(
            user_id=user.id, from_status=previous, to_status=target, actor_id=actor.id, reason=payload.get("reason")
        )
    )
    db.flush()
    write_audit(db, actor, "SET_USER_STATUS", "User", user.id, before={"status": previous}, after={"status": target}, request=request)
    db.commit()
    return {"message": "Status updated"}


@router.get("/permissions/catalogue")
def permission_catalogue(_: User = Depends(require_permission("users", "view"))):
    return [
        {"code": code, "name": name, "actions": actions}
        for code, name, actions in MODULES
    ]


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit", "view")),
):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "actor": row.actor_user_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "before": row.before_json,
            "after": row.after_json,
            "ip": row.ip,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
