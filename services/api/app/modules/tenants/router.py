"""Admin portal: companies and their first Company Admin. Platform Admins only."""

import re
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.deps import Auth, require_platform_admin
from app.core.email import send_email
from app.core.errors import conflict, not_found
from app.core.security import hash_token, new_token, utcnow
from app.modules.audit import service as audit
from app.modules.auth.models import Invitation
from app.modules.tenants.models import Company
from app.modules.tenants.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    InvitationOut,
    InviteAdmin,
)
from app.modules.users.models import COMPANY_ADMIN, User, UserRole

router = APIRouter(prefix="/admin/companies", tags=["admin: companies"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "company"


async def _user_counts(auth: Auth) -> dict[uuid.UUID, int]:
    rows = await auth.db.execute(
        select(User.company_id, func.count())
        .where(User.company_id.is_not(None), User.status != "deactivated")
        .group_by(User.company_id)
    )
    return {company_id: count for company_id, count in rows if company_id}


def _out(company: Company, user_count: int = 0) -> CompanyOut:
    return CompanyOut.model_validate(
        {**{c: getattr(company, c) for c in CompanyOut.model_fields if c != "user_count"},
         "user_count": user_count})


async def _get(auth: Auth, company_id: uuid.UUID) -> Company:
    company = await auth.db.get(Company, company_id)
    if company is None:
        raise not_found("Company not found.")
    return company


@router.get("", response_model=list[CompanyOut])
async def list_companies(auth: Auth = Depends(require_platform_admin)) -> list[CompanyOut]:
    counts = await _user_counts(auth)
    companies = await auth.db.scalars(select(Company).order_by(Company.name))
    return [_out(c, counts.get(c.id, 0)) for c in companies]


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(body: CompanyCreate,
                         auth: Auth = Depends(require_platform_admin)) -> CompanyOut:
    company = Company(name=body.name, slug=body.slug or _slugify(body.name),
                      limits=body.limits.model_dump())
    auth.db.add(company)
    try:
        await auth.db.flush()
    except IntegrityError as exc:
        raise conflict("A company with this slug already exists.") from exc
    await audit.record(auth.db, company_id=None, actor_user_id=auth.user.id,
                       action="company.created", entity_type="company", entity_id=company.id,
                       payload={"name": company.name, "slug": company.slug})
    await auth.db.commit()
    return _out(company)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: uuid.UUID,
                      auth: Auth = Depends(require_platform_admin)) -> CompanyOut:
    company = await _get(auth, company_id)
    return _out(company, (await _user_counts(auth)).get(company.id, 0))


@router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: uuid.UUID, body: CompanyUpdate,
                         auth: Auth = Depends(require_platform_admin)) -> CompanyOut:
    company = await _get(auth, company_id)
    changes = body.model_dump(exclude_none=True)
    if body.name is not None:
        company.name = body.name
    if body.status is not None:
        company.status = body.status
    if body.limits is not None:
        company.limits = body.limits.model_dump()
    await audit.record(auth.db, company_id=None, actor_user_id=auth.user.id,
                       action="company.updated", entity_type="company", entity_id=company.id,
                       payload=changes)
    await auth.db.commit()
    return _out(company, (await _user_counts(auth)).get(company.id, 0))


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: uuid.UUID,
                         auth: Auth = Depends(require_platform_admin)) -> None:
    company = await _get(auth, company_id)
    await audit.record(auth.db, company_id=None, actor_user_id=auth.user.id,
                       action="company.deleted", entity_type="company", entity_id=company.id,
                       payload={"name": company.name, "slug": company.slug})
    await auth.db.delete(company)
    await auth.db.commit()


@router.post("/{company_id}/invite-admin", response_model=InvitationOut,
             status_code=status.HTTP_201_CREATED)
async def invite_company_admin(company_id: uuid.UUID, body: InviteAdmin,
                               auth: Auth = Depends(require_platform_admin)) -> InvitationOut:
    """Invite a Company Admin by email. Re-inviting a pending user issues a fresh link."""
    settings = get_settings()
    company = await _get(auth, company_id)
    email = body.email.lower()

    user = await auth.db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(company_id=company.id, email=email, full_name=body.full_name,
                    status="invited", roles=[UserRole(role=COMPANY_ADMIN)])
        auth.db.add(user)
        await auth.db.flush()
    elif user.company_id != company.id or user.status != "invited":
        raise conflict("This email is already registered.")
    else:
        # Expire any earlier links for this user.
        await auth.db.execute(
            update(Invitation)
            .where(Invitation.user_id == user.id, Invitation.accepted_at.is_(None))
            .values(expires_at=utcnow())
        )

    token = new_token()
    invitation = Invitation(
        company_id=company.id, user_id=user.id, token_hash=hash_token(token),
        invited_by=auth.user.id,
        expires_at=utcnow() + timedelta(seconds=settings.invitation_ttl_seconds),
    )
    auth.db.add(invitation)
    await auth.db.flush()
    await audit.record(auth.db, company_id=None, actor_user_id=auth.user.id,
                       action="company.admin_invited", entity_type="user", entity_id=user.id,
                       payload={"company_id": str(company.id), "email": email})
    await auth.db.commit()

    days = settings.invitation_ttl_seconds // 86400
    await send_email(
        email,
        f"You're invited to administer {company.name} on Persona Forge",
        f"You've been invited as the Company Admin for {company.name}.\n\n"
        f"Accept the invitation: {settings.web_origin}/invite/{token}\n\n"
        f"This link expires in {days} days.",
    )
    return InvitationOut(invitation_id=invitation.id, user_id=user.id, email=email,
                         expires_at=invitation.expires_at)
