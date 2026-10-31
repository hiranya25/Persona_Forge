"""Imports every model so SQLAlchemy's metadata (and Alembic) sees all tables."""

from app.modules.audit.models import AuditLog
from app.modules.auth.models import Invitation, MfaMethod, OtpCode, RecoveryCode, RefreshToken
from app.modules.tenants.models import Company
from app.modules.users.models import User, UserRole

__all__ = [
    "AuditLog",
    "Company",
    "Invitation",
    "MfaMethod",
    "OtpCode",
    "RecoveryCode",
    "RefreshToken",
    "User",
    "UserRole",
]
