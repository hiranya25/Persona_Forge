import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import REFRESH_COOKIE, clear_session_cookies
from app.core.db import DbContext, open_session, system_session
from app.core.deps import Auth, authenticate, current_auth
from app.core.errors import bad_request, conflict, not_found, unauthorized
from app.core.ratelimit import rate_limiter
from app.core.security import (
    create_mfa_token,
    decode_mfa_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_token,
    new_totp_secret,
    password_needs_rehash,
    totp_matches,
    totp_uri,
    utcnow,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.auth import service
from app.modules.auth.models import Invitation, MfaMethod, RefreshToken
from app.modules.auth.schemas import (
    AcceptInvitation,
    ChangePassword,
    EmailSetupStarted,
    InvitationInfo,
    LoginResult,
    MeOut,
    MfaMethodOut,
    MfaSetupConfirm,
    MfaSetupStart,
    MfaTokenBody,
    MfaVerify,
    OtpRequest,
    OtpVerify,
    PasswordLogin,
    RecoveryCodesOut,
    TotpSetupStarted,
)
from app.modules.tenants.models import Company
from app.modules.users.models import User

router = APIRouter(tags=["auth"])

INVALID_LOGIN = "Invalid email or password."


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --- Password sign-in ------------------------------------------------------------------

@router.post("/auth/login", response_model=LoginResult, response_model_exclude_none=True)
async def login(body: PasswordLogin, request: Request, response: Response,
                db: AsyncSession = Depends(system_session)) -> LoginResult:
    email = body.email.lower()
    await rate_limiter.hit(f"login:ip:{_ip(request)}", 30, 300)
    await rate_limiter.hit(f"login:email:{email}", 10, 900)

    user = await service.find_user_by_email(db, email)
    if user is None or not verify_password(user.password_hash, body.password):
        if user is not None:
            await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                               action="auth.login_failed", entity_type="user",
                               entity_id=user.id, payload={"method": "password"})
            await db.commit()
        raise unauthorized(INVALID_LOGIN)
    await service.ensure_can_sign_in(db, user)

    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    if user.is_admin:
        await db.commit()
        return await service.second_factor_step(db, user)
    return await service.complete_sign_in(db, user, response, "password")


# --- Email-code sign-in (non-admin users) -------------------------------------------------

@router.post("/auth/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(body: OtpRequest, request: Request,
                      db: AsyncSession = Depends(system_session)) -> dict[str, str]:
    email = body.email.lower()
    await rate_limiter.hit(f"otp:ip:{_ip(request)}", 20, 900)
    await rate_limiter.hit(f"otp:email:{email}", 5, 900)

    user = await service.find_user_by_email(db, email)
    # Same response whether or not the account exists or may use email codes.
    if user is not None and not user.is_admin:
        try:
            await service.ensure_can_sign_in(db, user)
        except Exception:  # noqa: BLE001, S110 - never reveal account state
            pass
        else:
            await service.send_otp(db, user, "login")
    return {"detail": "If that account can sign in with an email code, a code has been sent."}


@router.post("/auth/otp/verify", response_model=LoginResult, response_model_exclude_none=True)
async def verify_otp(body: OtpVerify, request: Request, response: Response,
                     db: AsyncSession = Depends(system_session)) -> LoginResult:
    email = body.email.lower()
    await rate_limiter.hit(f"otp-verify:email:{email}", 10, 900)
    user = await service.find_user_by_email(db, email)
    if user is None or user.is_admin:
        raise unauthorized(service.INVALID_CODE)
    await service.ensure_can_sign_in(db, user)
    await service.consume_otp(db, user.id, "login", body.code)
    return await service.complete_sign_in(db, user, response, "email_otp")


# --- Second factor for admins ------------------------------------------------------------

async def _mfa_user(db: AsyncSession, token: str, purpose: str) -> User:
    user_id = decode_mfa_token(token, purpose)
    user = await db.get(User, user_id) if user_id else None
    if user is None:
        raise unauthorized("Your sign-in attempt expired. Please start again.")
    await service.ensure_can_sign_in(db, user)
    return user


@router.post("/auth/mfa/email/send", status_code=status.HTTP_204_NO_CONTENT)
async def send_mfa_email(body: MfaTokenBody,
                         db: AsyncSession = Depends(system_session)) -> None:
    user = await _mfa_user(db, body.mfa_token, "mfa")
    await rate_limiter.hit(f"mfa-email:{user.id}", 5, 900)
    if not any(m.type == "email_otp" for m in await service.confirmed_methods(db, user.id)):
        raise bad_request("Email codes aren't set up for this account.")
    await service.send_otp(db, user, "mfa")


@router.post("/auth/mfa/verify", response_model=LoginResult, response_model_exclude_none=True)
async def verify_mfa(body: MfaVerify, response: Response,
                     db: AsyncSession = Depends(system_session)) -> LoginResult:
    user = await _mfa_user(db, body.mfa_token, "mfa")
    await rate_limiter.hit(f"mfa-verify:{user.id}", 10, 900)
    method = await service.verify_second_factor(db, user, body.method, body.code)
    if method == "recovery_code":
        # A recovery code means a factor was lost: register a new one to finish signing in.
        await db.commit()
        return LoginResult(status="mfa_setup_required",
                           mfa_token=create_mfa_token(user.id, "mfa_setup"))
    return await service.complete_sign_in(db, user, response, method)


@asynccontextmanager
async def _setup_actor(request: Request, mfa_token: str | None) -> AsyncIterator[Auth]:
    """MFA setup works either mid-sign-in (with an ``mfa_setup`` token) or from a session."""
    if mfa_token:
        db = open_session(DbContext.system())
        try:
            user = await _mfa_user(db, mfa_token, "mfa_setup")
            yield Auth(user=user, db=db)
        finally:
            await db.close()
        return
    auth = await authenticate(request)
    try:
        yield auth
    finally:
        await auth.db.close()


@router.post("/auth/mfa/setup/totp/start", response_model=TotpSetupStarted)
async def start_totp_setup(body: MfaSetupStart, request: Request) -> TotpSetupStarted:
    async with _setup_actor(request, body.mfa_token) as auth:
        service.require_admin(auth.user)
        await _drop_pending(auth.db, auth.user.id)
        secret = new_totp_secret()
        method = MfaMethod(user_id=auth.user.id, type="totp",
                           label=body.label or "Authenticator app",
                           credential=encrypt_secret(secret))
        auth.db.add(method)
        await auth.db.commit()
        return TotpSetupStarted(method_id=method.id, secret=secret,
                                otpauth_uri=totp_uri(secret, auth.user.email))


@router.post("/auth/mfa/setup/email/start", response_model=EmailSetupStarted)
async def start_email_setup(body: MfaSetupStart, request: Request) -> EmailSetupStarted:
    async with _setup_actor(request, body.mfa_token) as auth:
        service.require_admin(auth.user)
        await rate_limiter.hit(f"mfa-setup-email:{auth.user.id}", 5, 900)
        await _drop_pending(auth.db, auth.user.id)
        method = MfaMethod(user_id=auth.user.id, type="email_otp",
                           label=body.label or "Email code")
        auth.db.add(method)
        await auth.db.flush()
        await service.send_otp(auth.db, auth.user, "mfa_setup")
        return EmailSetupStarted(method_id=method.id)


@router.post("/auth/mfa/setup/confirm", response_model=LoginResult,
             response_model_exclude_none=True)
async def confirm_mfa_setup(body: MfaSetupConfirm, request: Request,
                            response: Response) -> LoginResult:
    async with _setup_actor(request, body.mfa_token) as auth:
        db, user = auth.db, auth.user
        service.require_admin(user)
        await rate_limiter.hit(f"mfa-setup-confirm:{user.id}", 10, 900)
        method = await db.scalar(select(MfaMethod).where(
            MfaMethod.id == body.method_id, MfaMethod.user_id == user.id,
            MfaMethod.confirmed_at.is_(None)))
        if method is None:
            raise not_found("Setup not found. Please start again.")

        if method.type == "email_otp":
            await service.consume_otp(db, user.id, "mfa_setup", body.code)
        elif not (method.credential and totp_matches(
                decrypt_secret(method.credential), body.code)):
            raise unauthorized(service.INVALID_CODE)

        method.confirmed_at = utcnow()
        await audit.record(db, company_id=user.company_id, actor_user_id=user.id,
                           action="auth.mfa_method_added", entity_type="mfa_method",
                           entity_id=method.id, payload={"type": method.type})
        codes = None
        if not await service.has_unused_recovery_codes(db, user.id):
            codes = await service.issue_recovery_codes(db, user)

        if body.mfa_token:
            await service.issue_session(db, user, response, f"{method.type}_setup")
        await db.commit()
        return LoginResult(status="ok", user=await service.me_out(db, user),
                           recovery_codes=codes)


async def _drop_pending(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(MfaMethod).where(MfaMethod.user_id == user_id,
                                             MfaMethod.confirmed_at.is_(None)))


# --- Session refresh / sign-out ----------------------------------------------------------

@router.post("/auth/refresh", response_model=MeOut)
async def refresh(request: Request, response: Response,
                  db: AsyncSession = Depends(system_session)) -> MeOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise unauthorized("Session expired.")
    user = await service.rotate_refresh_token(db, raw, response)
    return await service.me_out(db, user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response,
                 db: AsyncSession = Depends(system_session)) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        token = await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
        if token is not None:
            await service.revoke_family(db, token.family_id)
            await db.commit()
    clear_session_cookies(response)


# --- Invitations -------------------------------------------------------------------------

async def _open_invitation(db: AsyncSession, token: str) -> tuple[Invitation, User, Company]:
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if (invitation is None or invitation.accepted_at is not None
            or invitation.expires_at <= utcnow()):
        raise not_found("This invitation is invalid or has expired.")
    user = await db.get(User, invitation.user_id)
    company = await db.get(Company, invitation.company_id)
    if user is None or company is None:
        raise not_found("This invitation is invalid or has expired.")
    return invitation, user, company


@router.get("/invitations/{token}", response_model=InvitationInfo)
async def get_invitation(token: str,
                         db: AsyncSession = Depends(system_session)) -> InvitationInfo:
    invitation, user, company = await _open_invitation(db, token)
    return InvitationInfo(email=user.email, company_name=company.name,
                          expires_at=invitation.expires_at)


@router.post("/invitations/{token}/accept", response_model=LoginResult,
             response_model_exclude_none=True)
async def accept_invitation(token: str, body: AcceptInvitation, response: Response,
                            db: AsyncSession = Depends(system_session)) -> LoginResult:
    invitation, user, company = await _open_invitation(db, token)
    if user.status != "invited":
        raise conflict("This account is already active.")
    invitation.accepted_at = utcnow()
    user.full_name = body.full_name
    user.password_hash = hash_password(body.password)
    user.status = "active"
    await audit.record(db, company_id=company.id, actor_user_id=user.id,
                       action="user.invitation_accepted", entity_type="user", entity_id=user.id)
    await service.ensure_can_sign_in(db, user)
    if user.is_admin:
        await db.commit()
        return await service.second_factor_step(db, user)
    return await service.complete_sign_in(db, user, response, "invitation")


# --- Current user ------------------------------------------------------------------------

@router.get("/me", response_model=MeOut)
async def get_me(auth: Auth = Depends(current_auth)) -> MeOut:
    return await service.me_out(auth.db, auth.user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePassword, auth: Auth = Depends(current_auth)) -> None:
    await rate_limiter.hit(f"password-change:{auth.user.id}", 10, 900)
    if not verify_password(auth.user.password_hash, body.current_password):
        raise unauthorized("Your current password is incorrect.")
    auth.user.password_hash = hash_password(body.new_password)
    await audit.record(auth.db, company_id=auth.user.company_id, actor_user_id=auth.user.id,
                       action="user.password_changed", entity_type="user",
                       entity_id=auth.user.id)
    await auth.db.commit()


@router.get("/me/mfa-methods", response_model=list[MfaMethodOut])
async def list_mfa_methods(auth: Auth = Depends(current_auth)) -> list[MfaMethodOut]:
    return [MfaMethodOut.model_validate(m, from_attributes=True)
            for m in await service.confirmed_methods(auth.db, auth.user.id)]


@router.delete("/me/mfa-methods/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mfa_method(method_id: uuid.UUID, auth: Auth = Depends(current_auth)) -> None:
    methods = await service.confirmed_methods(auth.db, auth.user.id)
    method = next((m for m in methods if m.id == method_id), None)
    if method is None:
        raise not_found()
    if auth.user.is_admin and len(methods) == 1:
        raise conflict("Admins must keep at least one second factor. Add another one first.")
    await auth.db.delete(method)
    await audit.record(auth.db, company_id=auth.user.company_id, actor_user_id=auth.user.id,
                       action="auth.mfa_method_removed", entity_type="mfa_method",
                       entity_id=method.id, payload={"type": method.type})
    await auth.db.commit()


@router.post("/me/recovery-codes", response_model=RecoveryCodesOut)
async def regenerate_recovery_codes(auth: Auth = Depends(current_auth)) -> RecoveryCodesOut:
    service.require_admin(auth.user)
    codes = await service.issue_recovery_codes(auth.db, auth.user)
    await auth.db.commit()
    return RecoveryCodesOut(recovery_codes=codes)
