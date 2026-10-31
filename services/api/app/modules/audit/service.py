"""Hash-chained audit log.

``hash = SHA-256(prev_hash || canonical JSON of the entry)``. Editing or deleting
any entry breaks every hash after it, which ``verify_chain`` detects.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.modules.audit.models import AuditLog

GENESIS_HASH = "0" * 64
PLATFORM_CHAIN = "platform"


def chain_key_for(company_id: uuid.UUID | None) -> str:
    return str(company_id) if company_id else PLATFORM_CHAIN


def _canonical(entry: AuditLog) -> str:
    created_at: datetime = entry.created_at
    return json.dumps(
        {
            "chain_key": entry.chain_key,
            "company_id": str(entry.company_id) if entry.company_id else None,
            "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
            "actor_type": entry.actor_type,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "payload": entry.payload,
            "created_at": created_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_hash(prev_hash: str, entry: AuditLog) -> str:
    return hashlib.sha256((prev_hash + _canonical(entry)).encode()).hexdigest()


async def record(
    db: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an entry to the company's chain (or the platform chain) in the current
    transaction, so the entry commits or rolls back together with the change it describes."""
    chain_key = chain_key_for(company_id)
    # Serialise appends per chain so concurrent writers can't fork it.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                     {"k": chain_key})
    prev_hash = await db.scalar(
        select(AuditLog.hash).where(AuditLog.chain_key == chain_key)
        .order_by(AuditLog.id.desc()).limit(1)
    ) or GENESIS_HASH

    entry = AuditLog(
        chain_key=chain_key,
        company_id=company_id,
        actor_user_id=actor_user_id,
        actor_type="user" if actor_user_id else "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        payload=payload or {},
        created_at=utcnow(),
        prev_hash=prev_hash,
    )
    entry.hash = compute_hash(prev_hash, entry)
    db.add(entry)
    await db.flush()
    return entry


@dataclass
class ChainVerification:
    chain_key: str
    entries_checked: int
    valid: bool
    first_broken_id: int | None = None
    reason: str | None = None


async def verify_chain(db: AsyncSession, company_id: uuid.UUID | None) -> ChainVerification:
    chain_key = chain_key_for(company_id)
    result = await db.stream_scalars(
        select(AuditLog).where(AuditLog.chain_key == chain_key).order_by(AuditLog.id)
    )
    prev_hash = GENESIS_HASH
    checked = 0
    async for entry in result:
        checked += 1
        if entry.prev_hash != prev_hash:
            return ChainVerification(chain_key, checked, False, entry.id,
                                     "An entry is missing or out of order before this one.")
        if compute_hash(prev_hash, entry) != entry.hash:
            return ChainVerification(chain_key, checked, False, entry.id,
                                     "This entry's contents were changed.")
        prev_hash = entry.hash
    return ChainVerification(chain_key, checked, True)


async def list_entries(
    db: AsyncSession, company_id: uuid.UUID | None, limit: int, before_id: int | None
) -> tuple[list[AuditLog], int | None]:
    query = select(AuditLog).where(AuditLog.chain_key == chain_key_for(company_id))
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    rows = list(await db.scalars(query.order_by(AuditLog.id.desc()).limit(limit + 1)))
    next_cursor = rows[limit - 1].id if len(rows) > limit else None
    return rows[:limit], next_cursor

