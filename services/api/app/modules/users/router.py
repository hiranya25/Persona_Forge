"""Company portal: the Company Admin manages their team."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import Auth, require_roles
from app.core.errors import conflict, not_found
from app.core.security import hash_password
from app.modules.audit import service as audit
from app.modules.auth.service import revoke_all_sessions
from app.modules.tenants.models import Company
from app.modules.users.models import COMPANY_ADMIN, User, UserRole
from app.modules.users.schemas import PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["company: users"])
company_admin = require_roles(COMPANY_ADMIN)


def _out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name,
                   roles=user.role_names, status=user.status,
                   last_login_at=user.last_login_at, created_at=user.created_at)


async def _get(auth: Auth, user_id: uuid.UUID) -> User:
    # Row-Level Security already hides other companies' users; the explicit
    # filter keeps the intent obvious.
    user = await auth.db.scalar(
        select(User).where(User.id == user_id, User.company_id == auth.company_id))
    if user is None:
        raise not_found("User not found.")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(auth: Auth = Depends(company_admin)) -> list[UserOut]:
    users = await auth.db.scalars(
        select(User).where(User.company_id == auth.company_id).order_by(User.email))
    return [_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, auth: Auth = Depends(company_admin)) -> UserOut:
    company = await auth.db.get(Company, auth.company_id)
    assert company is not None
    active_users = await auth.db.scalar(
        select(func.count()).select_from(User)
        .where(User.company_id == auth.company_id, User.status != "deactivated"))
    if (active_users or 0) >= company.limits.get("max_users", 0):
        raise conflict("Your company has reached its user limit.")

    user = User(company_id=auth.company_id, email=body.email.lower(), full_name=body.full_name,
                password_hash=hash_password(body.password), status="active",
                roles=[UserRole(role=r) for r in sorted(set(body.roles))])
    auth.db.add(user)
    try:
        await auth.db.flush()
    except IntegrityError as exc:
        raise conflict("This email is already registered.") from exc
    await audit.record(auth.db, company_id=auth.company_id, actor_user_id=auth.user.id,
                       action="user.created", entity_type="user", entity_id=user.id,
                       payload={"email": user.email, "roles": user.role_names})
    await auth.db.commit()
    await auth.db.refresh(user)
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate,
                      auth: Auth = Depends(company_admin)) -> UserOut:
    user = await _get(auth, user_id)
    is_self = user.id == auth.user.id
    if is_self and body.status == "deactivated":
        raise conflict("You can't deactivate your own account.")
    if is_self and body.roles is not None and COMPANY_ADMIN not in body.roles:
        raise conflict("You can't remove your own Company Admin role.")

    changes = body.model_dump(exclude_none=True)
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.roles is not None:
        user.roles = [UserRole(role=r) for r in sorted(set(body.roles))]
    if body.status is not None and body.status != user.status:
        if user.status == "invited":
            raise conflict("This user hasn't accepted their invitation yet.")
        user.status = body.status
        if body.status == "deactivated":
            await revoke_all_sessions(auth.db, user.id)
    await audit.record(auth.db, company_id=auth.company_id, actor_user_id=auth.user.id,
                       action="user.updated", entity_type="user", entity_id=user.id,
                       payload=changes)
    await auth.db.commit()
    await auth.db.refresh(user)
    return _out(user)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(user_id: uuid.UUID, body: PasswordReset,
                         auth: Auth = Depends(company_admin)) -> None:
    user = await _get(auth, user_id)
    user.password_hash = hash_password(body.password)
    await revoke_all_sessions(auth.db, user.id)
    await audit.record(auth.db, company_id=auth.company_id, actor_user_id=auth.user.id,
                       action="user.password_reset", entity_type="user", entity_id=user.id)
    await auth.db.commit()
