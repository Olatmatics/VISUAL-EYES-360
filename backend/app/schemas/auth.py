from pydantic import BaseModel, Field, field_validator


def _strong_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isupper() for c in value) or not any(c.islower() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Password must include upper, lower and numeric characters")
    return value


class SetupAdminRequest(BaseModel):
    setup_token: str
    full_name: str = Field(min_length=2, max_length=180)
    user_id: str = Field(min_length=3, max_length=80)
    password: str
    confirm_password: str
    phone: str | None = None
    email: str | None = None
    recovery_info: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _strong_password(value)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password and value != password:
            raise ValueError("Passwords do not match")
        return value


class LoginRequest(BaseModel):
    user_id: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new(cls, value: str) -> str:
        return _strong_password(value)


class ForgotPasswordRequest(BaseModel):
    user_id: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new(cls, value: str) -> str:
        return _strong_password(value)


class UserContext(BaseModel):
    id: str
    user_id: str
    full_name: str
    role: str
    is_super_admin: bool
    permissions: list[str]
    stations: list[str]
    all_stations: bool
    must_change_password: bool = False
    role_code: str | None = None
    scope_state_id: str | None = None
    scope_lga_id: str | None = None
    department: str | None = None
    position: str | None = None
    staff_id: str | None = None
