"""Sign-in flows.

* Admins (Platform Admin, Company Admin): password, then a mandatory second factor
  (authenticator app or email code), with one-time recovery codes as backup.
* Everyone else: password, or a one-time code sent by email.
"""

import uuid
from datetime import timedelta

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.cookies import set_session_cookies
from app.core.email import send_email
from app.core.errors import ProblemError, bad_request, forbidden, unauthorized
from app.core.security import (
    create_access_token,
    create_mfa_token,
    decrypt_secret,
    hash_otp,
    hash_token,
    new_otp,
    new_recovery_codes,
    new_token,
    normalize_recovery_code,
    otp_matches,
    totp_matches,
    utcnow,
)
from app.modules.audit import service as audit
from app.modules.auth.models import MfaMethod, OtpCode, RecoveryCode, RefreshToken
from app.modules.auth.schemas import CompanyRef, LoginResult, MeOut
from app.modules.tenants.models import Company
from app.modules.users.models import User

INVALID_CODE = "The code is invalid or has expired."


async def me_out(db: AsyncSession, user: User) -> MeOut:
    company = await db.get(Company, user.company_id) if user.company_id else None
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_platform_admin=user.is_platform_admin,
        roles=user.role_names,
        company=CompanyRef(id=company.id, name=company.name, slug=company.slug)
        if company else None,
    )


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.strip().lower()))


async def ensure_can_sign_in(db: AsyncSession, user: User) -> None:
    if user.status != "active":
        raise unauthorized("This account is not active.")
    if user.company_id is not None:
        company = await db.get(Company, user.company_id)
        if company is None or company.status != "active":
            raise forbidden("This company's access is suspended.")


async def confirmed_methods(db: AsyncSession, user_id: uuid.UUID) -> list[MfaMethod]:
    return list(await db.scalars(
        select(MfaMethod)
        .where(MfaMethod.user_id == user_id, MfaMethod.confirmed_at.is_not(None))
        .order_by(MfaMethod.created_at)
    ))


# --- Sessions ------------------------------------------------------------------

async def issue_session(db: AsyncSession, user: User, response: Response, method: str,
                        family_id: uuid.UUID | None = None) -> None:
    """Create a refresh token (in a new or existing family) and set session cookies."""
    settings = get_settings()
    refresh = new_token()
    db.add(RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(refresh),
        expires_at=utcnow() + timedelta(seconds=settings.refresh_token_ttl_seconds),
    ))
    access = create_access_token(user.id, user.company_id, user.is_platform_admin,
                                 user.role_names)
    if family_id is None:
        user.last_login_at = utcnow()
        await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                           action="auth.login", entity_type="user", entity_id=user.id,
                           payload={"method": method})
    set_session_cookies(response, access, refresh)


async def complete_sign_in(db: AsyncSession, user: User, response: Response,
                           method: str) -> LoginResult:
    await issue_session(db, user, response, method)
    await db.commit()
    return LoginResult(status="ok", user=await me_out(db, user))


async def second_factor_step(db: AsyncSession, user: User) -> LoginResult:
    """After a correct password, tell an admin which second factor to use next."""
    methods = await confirmed_methods(db, user.id)
    if not methods:
        return LoginResult(status="mfa_setup_required",
                           mfa_token=create_mfa_token(user.id, "mfa_setup"))
    return LoginResult(status="mfa_required",
                       mfa_token=create_mfa_token(user.id, "mfa"),
                       methods=sorted({m.type for m in methods}))


async def rotate_refresh_token(db: AsyncSession, raw_token: str, response: Response) -> User:
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None:
        raise unauthorized("Session expired.")
    user = await db.get(User, token.user_id)
    if user is None:
        raise unauthorized("Session expired.")

    if token.revoked_at is not None:
        # A rotated-out token was used again: it was probably stolen. End the session.
        await revoke_family(db, token.family_id)
        await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                           action="auth.refresh_token_reused", entity_type="user",
                           entity_id=user.id)
        await db.commit()
        raise unauthorized("Session expired.")
    if token.expires_at <= utcnow():
        raise unauthorized("Session expired.")

    await ensure_can_sign_in(db, user)
    token.revoked_at = utcnow()
    await issue_session(db, user, response, "refresh", family_id=token.family_id)
    await db.commit()
    return user


async def revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# --- Email one-time codes ----------------------------------------------------------

async def send_otp(db: AsyncSession, user: User, purpose: str) -> None:
    settings = get_settings()
    # Only the newest code is valid.
    await db.execute(
        update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == purpose,
               OtpCode.used_at.is_(None))
        .values(used_at=utcnow())
    )
    code = new_otp()
    db.add(OtpCode(user_id=user.id, purpose=purpose, code_hash=hash_otp(code),
                   expires_at=utcnow() + timedelta(seconds=settings.otp_ttl_seconds)))
    await db.commit()
    minutes = settings.otp_ttl_seconds // 60
    await send_email(
        user.email,
        "Your Persona Forge sign-in code",
        f"Your code is {code}. It expires in {minutes} minutes.\n\n"
        "If you didn't try to sign in, you can ignore this email.",
    )


async def consume_otp(db: AsyncSession, user_id: uuid.UUID, purpose: str, code: str) -> None:
    """Accept the newest unexpired code for ``purpose`` or raise. Failed attempts are
    committed before raising, so the attempt limit holds."""
    otp = await db.scalar(
        select(OtpCode)
        .where(OtpCode.user_id == user_id, OtpCode.purpose == purpose,
               OtpCode.used_at.is_(None), OtpCode.expires_at > utcnow())
        .order_by(OtpCode.created_at.desc()).limit(1).with_for_update()
    )
    if otp is None or otp.attempts >= get_settings().otp_max_attempts:
        raise unauthorized(INVALID_CODE)
    otp.attempts += 1
    if not otp_matches(code, otp.code_hash):
        await db.commit()
        raise unauthorized(INVALID_CODE)
    otp.used_at = utcnow()


# --- Second factors -----------------------------------------------------------------

async def verify_second_factor(db: AsyncSession, user: User, method: str, code: str) -> str:
    """Check a second-factor code. Returns the method actually used."""
    if method == "recovery_code":
        recovery = await db.scalar(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == hash_token(normalize_recovery_code(code)),
                RecoveryCode.used_at.is_(None),
            ).with_for_update()
        )
        if recovery is None:
            raise unauthorized(INVALID_CODE)
        recovery.used_at = utcnow()
        await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                           action="auth.recovery_code_used", entity_type="user",
                           entity_id=user.id)
        return method

    methods = [m for m in await confirmed_methods(db, user.id) if m.type == method]
    if not methods:
        raise bad_request("This sign-in method isn't set up for your account.")
    if method == "email_otp":
        await consume_otp(db, user.id, "mfa", code)
        methods[0].last_used_at = utcnow()
        return method
    for candidate in methods:
        if candidate.credential and totp_matches(decrypt_secret(candidate.credential), code):
            candidate.last_used_at = utcnow()
            return method
    raise unauthorized(INVALID_CODE)


async def issue_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    """Replace any existing recovery codes with a fresh set (shown to the user once)."""
    await db.execute(
        update(RecoveryCode)
        .where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
        .values(used_at=utcnow())
    )
    codes = new_recovery_codes()
    db.add_all(RecoveryCode(user_id=user.id, code_hash=hash_token(c)) for c in codes)
    await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                       action="auth.recovery_codes_generated", entity_type="user",
                       entity_id=user.id)
    return codes


async def has_unused_recovery_codes(db: AsyncSession, user_id: uuid.UUID) -> bool:
    return await db.scalar(
        select(RecoveryCode.id)
        .where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None)).limit(1)
    ) is not None


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise ProblemError(403, "Forbidden",
                           "Second factors are used by admin accounts only.")
