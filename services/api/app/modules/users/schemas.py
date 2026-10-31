import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.security import MIN_PASSWORD_LENGTH

Role = Literal["company_admin", "analyst", "reviewer", "viewer"]


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    roles: list[Role] = Field(min_length=1)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    roles: list[Role] | None = Field(default=None, min_length=1)
    status: Literal["active", "deactivated"] | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    status: str
    last_login_at: datetime | None
    created_at: datetime
