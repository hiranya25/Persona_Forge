"""Authentication and authorization dependencies."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE
from app.core.db import DbContext, open_session
from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token
from app.modules.tenants.models import Company
from app.modules.users.models import User


@dataclass
class Auth:
    """The signed-in user plus a database session scoped to what they may see."""

    user: User
    db: AsyncSession

    @property
    def company_id(self) -> uuid.UUID:
        assert self.user.company_id is not None
        return self.user.company_id


async def authenticate(request: Request) -> Auth:
    """Resolve the access cookie into an active user and a tenant-scoped session.
    The caller owns the returned session and must close it."""
    token = request.cookies.get(ACCESS_COOKIE)
    claims = decode_access_token(token) if token else None
    if not claims:
        raise unauthorized()

    company_id = uuid.UUID(claims["cid"]) if claims.get("cid") else None
    ctx = DbContext.tenant(company_id) if company_id else DbContext.platform()
    db = open_session(ctx)
    try:
        user = await db.get(User, uuid.UUID(claims["sub"]))
        if user is None or user.status != "active":
            raise unauthorized("This account is not active.")
        if company_id is not None:
            company = await db.get(Company, company_id)
            if company is None or company.status != "active":
                raise forbidden("This company's access is suspended.")
    except BaseException:
        await db.close()
        raise
    return Auth(user=user, db=db)


async def current_auth(request: Request) -> AsyncIterator[Auth]:
    auth = await authenticate(request)
    try:
        yield auth
    finally:
        await auth.db.close()


def require_roles(*roles: str) -> Callable[..., Awaitable[Auth]]:
    """Allow company users holding at least one of ``roles``."""

    async def dependency(auth: Auth = Depends(current_auth)) -> Auth:
        if auth.user.is_platform_admin or not set(roles) & set(auth.user.role_names):
            raise forbidden()
        return auth

    return dependency


async def require_platform_admin(auth: Auth = Depends(current_auth)) -> Auth:
    if not auth.user.is_platform_admin:
        raise forbidden()
    return auth
