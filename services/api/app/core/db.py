"""Database engine, sessions, and the tenant context used by Row-Level Security.

Every transaction begins by setting two transaction-local Postgres settings:

* ``app.scope``      - ``tenant``, ``platform``, ``system``, or ``none``
* ``app.company_id`` - the current company's id (tenant scope only)

The RLS policies in the migrations read these settings, so even a query that
forgets its ``company_id`` filter cannot return another company's rows.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import get_settings

Scope = Literal["tenant", "platform", "system", "none"]


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True)
class DbContext:
    scope: Scope
    company_id: uuid.UUID | None = None

    @classmethod
    def tenant(cls, company_id: uuid.UUID) -> "DbContext":
        return cls("tenant", company_id)

    @classmethod
    def platform(cls) -> "DbContext":
        return cls("platform")

    @classmethod
    def system(cls) -> "DbContext":
        return cls("system")


_engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _apply_context(session: Session, transaction: object, connection: object) -> None:
    ctx: DbContext = session.info.get("ctx", DbContext("none"))
    connection.execute(  # type: ignore[attr-defined]
        text(
            "SELECT set_config('app.scope', :scope, true), "
            "set_config('app.company_id', :company_id, true)"
        ),
        {"scope": ctx.scope, "company_id": str(ctx.company_id) if ctx.company_id else ""},
    )


def open_session(ctx: DbContext) -> AsyncSession:
    session = SessionLocal()
    session.info["ctx"] = ctx
    return session


async def system_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for unauthenticated flows (login, invitations)."""
    async with open_session(DbContext.system()) as session:
        yield session
