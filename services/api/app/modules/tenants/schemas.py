import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class Limits(BaseModel):
    max_users: int = Field(default=25, ge=1, le=10_000)
    max_documents: int = Field(default=500, ge=1, le=1_000_000)
    queries_per_day: int = Field(default=500, ge=1, le=1_000_000)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)
    limits: Limits = Limits()


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Literal["active", "suspended"] | None = None
    limits: Limits | None = None


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    limits: Limits
    strictness: str
    share_labels: bool
    created_at: datetime
    user_count: int = 0


class InviteAdmin(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=200)


class InvitationOut(BaseModel):
    invitation_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    expires_at: datetime
