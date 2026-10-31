import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

DEFAULT_LIMITS: dict[str, int] = {"max_users": 25, "max_documents": 500, "queries_per_day": 500}


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="status_valid"),
        CheckConstraint("strictness IN ('lenient', 'standard', 'strict')",
                        name="strictness_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, default=lambda: dict(DEFAULT_LIMITS))
    strictness: Mapped[str] = mapped_column(String(20), default="standard")
    share_labels: Mapped[bool] = mapped_column(Boolean, default=False,
                                               server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
