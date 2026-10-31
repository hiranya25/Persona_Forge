import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.security import MIN_PASSWORD_LENGTH


class CompanyRef(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class MfaMethodOut(BaseModel):
    id: uuid.UUID
    type: str
    label: str
    created_at: datetime
    last_used_at: datetime | None


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_platform_admin: bool
    roles: list[str]
    company: CompanyRef | None


class LoginResult(BaseModel):
    """``ok``: signed in (cookies set). Otherwise the client continues with ``mfa_token``."""

    status: Literal["ok", "mfa_required", "mfa_setup_required"]
    user: MeOut | None = None
    mfa_token: str | None = None
    methods: list[str] | None = None
    recovery_codes: list[str] | None = None


class PasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class MfaTokenBody(BaseModel):
    mfa_token: str


class MfaVerify(BaseModel):
    mfa_token: str
    method: Literal["totp", "email_otp", "recovery_code"]
    code: str = Field(max_length=40)


class MfaSetupStart(BaseModel):
    mfa_token: str | None = None
    label: str = Field(default="", max_length=100)


class TotpSetupStarted(BaseModel):
    method_id: uuid.UUID
    secret: str
    otpauth_uri: str


class EmailSetupStarted(BaseModel):
    method_id: uuid.UUID


class MfaSetupConfirm(BaseModel):
    mfa_token: str | None = None
    method_id: uuid.UUID
    code: str = Field(max_length=10)


class InvitationInfo(BaseModel):
    email: str
    company_name: str
    expires_at: datetime


class AcceptInvitation(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]
