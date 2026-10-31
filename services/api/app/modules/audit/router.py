import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import Auth, require_platform_admin, require_roles
from app.modules.audit import service
from app.modules.audit.schemas import AuditEntryOut, AuditPage, VerificationOut
from app.modules.users.models import COMPANY_ADMIN, REVIEWER, VIEWER

router = APIRouter(tags=["audit"])
audit_readers = require_roles(COMPANY_ADMIN, REVIEWER, VIEWER)


async def _page(auth: Auth, company_id: uuid.UUID | None, limit: int,
                cursor: int | None) -> AuditPage:
    rows, next_cursor = await service.list_entries(auth.db, company_id, limit, cursor)
    return AuditPage(items=[AuditEntryOut.model_validate(r, from_attributes=True)
                            for r in rows],
                     next_cursor=next_cursor)


async def _verify(auth: Auth, company_id: uuid.UUID | None) -> VerificationOut:
    result = await service.verify_chain(auth.db, company_id)
    return VerificationOut(valid=result.valid, entries_checked=result.entries_checked,
                           first_broken_id=result.first_broken_id, reason=result.reason)


@router.get("/audit", response_model=AuditPage)
async def company_audit(limit: int = Query(50, ge=1, le=200), cursor: int | None = None,
                        auth: Auth = Depends(audit_readers)) -> AuditPage:
    return await _page(auth, auth.company_id, limit, cursor)


@router.post("/audit/verify", response_model=VerificationOut)
async def verify_company_audit(auth: Auth = Depends(audit_readers)) -> VerificationOut:
    return await _verify(auth, auth.company_id)


@router.get("/admin/audit", response_model=AuditPage, tags=["admin: audit"])
async def platform_audit(limit: int = Query(50, ge=1, le=200), cursor: int | None = None,
                         auth: Auth = Depends(require_platform_admin)) -> AuditPage:
    return await _page(auth, None, limit, cursor)


@router.post("/admin/audit/verify", response_model=VerificationOut, tags=["admin: audit"])
async def verify_platform_audit(
        auth: Auth = Depends(require_platform_admin)) -> VerificationOut:
    return await _verify(auth, None)
