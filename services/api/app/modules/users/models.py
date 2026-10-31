import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

COMPANY_ADMIN = "company_admin"
ANALYST = "analyst"
REVIEWER = "reviewer"
VIEWER = "viewer"
COMPANY_ROLES = (COMPANY_ADMIN, ANALYST, REVIEWER, VIEWER)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('invited', 'active', 'deactivated')", name="status_valid"),
        # Platform Admins belong to no company; everyone else belongs to exactly one.
        CheckConstraint("is_platform_admin = (company_id IS NULL)", name="tenant_matches_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200), default="")
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False,
                                                    server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())

    roles: Mapped[list["UserRole"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def role_names(self) -> list[str]:
        return sorted(r.role for r in self.roles)

    @property
    def is_admin(self) -> bool:
        """Admins must sign in with a password plus a second factor."""
        return self.is_platform_admin or COMPANY_ADMIN in self.role_names


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('company_admin', 'analyst', 'reviewer', 'viewer')", name="role_valid"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(30), primary_key=True)
