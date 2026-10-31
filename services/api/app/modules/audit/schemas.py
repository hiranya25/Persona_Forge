import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    actor_user_id: uuid.UUID | None
    actor_type: str
    action: str
    entity_type: str | None
    entity_id: str | None
    payload: dict[str, Any]
    created_at: datetime
    prev_hash: str
    hash: str


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    next_cursor: int | None


class VerificationOut(BaseModel):
    valid: bool
    entries_checked: int
    first_broken_id: int | None
    reason: str | None
