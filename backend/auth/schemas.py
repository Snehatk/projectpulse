"""Pydantic schemas for authentication, user management, and device pairing."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    email_or_username: str | None = None
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str
    role: str


class FirstRunCheckResponse(BaseModel):
    has_pm_account: bool
    total_users: int


class FirstRunPMSignup(BaseModel):
    email: str
    password: str = Field(min_length=6, description="Password must be at least 6 characters")
    name: str
    project_id: str = "PP"
    project_name: str = "Showcase Order Service"
    project_folder: str = ""


class UserCreateAdmin(BaseModel):
    email: str
    password: str = Field(min_length=6)
    name: str
    role: str  # DEVELOPER, TESTER, QA, PROJECT_MANAGER


class UserUpdateAdmin(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class PairingCodeGenerateResponse(BaseModel):
    pairing_code: str
    user_id: str
    role: str
    project_id: str
    expires_in_seconds: int = 600


class PairDeviceRequest(BaseModel):
    pairing_code: str
    machine_name: str = "LOCAL-PC"
    device_id: str | None = None


class PairDeviceResponse(BaseModel):
    device_token: str
    device_id: str
    user_id: str
    project_id: str
    role: str
    machine_name: str


class DeviceTokenResponse(BaseModel):
    id: int
    device_id: str
    user_id: str
    project_id: str
    role: str
    machine_name: str
    is_paired: bool
    is_revoked: bool
    created_at: datetime
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}
