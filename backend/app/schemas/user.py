from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.auth import _strong_password


class PermissionItem(BaseModel):
    module: str
    action: str
    effect: str = "GRANT"


class ManagerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    manager_id: str = Field(min_length=3, max_length=80)
    password: str
    confirm_password: str
    phone: str | None = None
    email: str | None = None
    station_ids: list[str] = Field(default_factory=list)
    all_stations: bool = False
    is_active: bool = True
    permissions: list[PermissionItem] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _strong_password(value)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm(cls, value: str, info) -> str:
        if info.data.get("password") and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class ManagerUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    station_ids: list[str] | None = None
    all_stations: bool | None = None
    is_active: bool | None = None
    permissions: list[PermissionItem] | None = None


class ManagerOut(BaseModel):
    id: str
    user_id: str
    full_name: str
    phone: str | None
    email: str | None
    is_active: bool
    all_stations: bool
    station_ids: list[str]
    permissions: list[str]
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
