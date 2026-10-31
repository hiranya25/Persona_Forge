"""Foundations: companies, users, auth, audit log, and Row-Level Security.

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
TABLES = ["companies", "users", "user_roles", "invitations", "refresh_tokens",
          "mfa_methods", "otp_codes", "recovery_codes", "audit_log"]


def _app_role() -> str:
    role = get_settings().app_db_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", role):
        raise ValueError(f"Invalid database role name: {role!r}")
    return role


def _user_fk() -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("limits", postgresql.JSONB, nullable=False),
        sa.Column("strictness", sa.String(20), nullable=False),
        sa.Column("share_labels", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_companies_status_valid"),
        sa.CheckConstraint("strictness IN ('lenient', 'standard', 'strict')",
                           name="ck_companies_strictness_valid"),
    )
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  index=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_platform_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_login_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('invited', 'active', 'deactivated')",
                           name="ck_users_status_valid"),
        sa.CheckConstraint("is_platform_admin = (company_id IS NULL)",
                           name="ck_users_tenant_matches_type"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("role", sa.String(30), primary_key=True),
        sa.CheckConstraint("role IN ('company_admin', 'analyst', 'reviewer', 'viewer')",
                           name="ck_user_roles_role_valid"),
    )
    op.create_table(
        "invitations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        _user_fk(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("accepted_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID, primary_key=True),
        _user_fk(),
        sa.Column("family_id", UUID, nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "mfa_methods",
        sa.Column("id", UUID, primary_key=True),
        _user_fk(),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("credential", sa.Text),
        sa.Column("confirmed_at", TS),
        sa.Column("last_used_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('totp', 'email_otp', 'passkey')",
                           name="ck_mfa_methods_type_valid"),
    )
    op.create_table(
        "otp_codes",
        sa.Column("id", UUID, primary_key=True),
        _user_fk(),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("used_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('login', 'mfa', 'mfa_setup')",
                           name="ck_otp_codes_purpose_valid"),
    )
    op.create_table(
        "recovery_codes",
        sa.Column("id", UUID, primary_key=True),
        _user_fk(),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", TS),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("chain_key", sa.String(40), nullable=False),
        sa.Column("company_id", UUID),
        sa.Column("actor_user_id", UUID),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(40)),
        sa.Column("entity_id", sa.String(80)),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_log_chain", "audit_log", ["chain_key", "id"])

    # --- Row-Level Security ---------------------------------------------------------
    # Each transaction sets app.scope and app.company_id (see app/core/db.py).
    op.execute("""
        CREATE FUNCTION app_scope() RETURNS text LANGUAGE sql STABLE AS
        $$ SELECT coalesce(nullif(current_setting('app.scope', true), ''), 'none') $$
    """)
    op.execute("""
        CREATE FUNCTION app_company_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.company_id', true), '')::uuid $$
    """)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # Platform Admins see company metadata; tenants see only their own company.
    for table, column in [("companies", "id"), ("users", "company_id"),
                          ("invitations", "company_id")]:
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (app_scope() IN ('platform', 'system') OR {column} = app_company_id())
            WITH CHECK (app_scope() IN ('platform', 'system') OR {column} = app_company_id())
        """)
    # Roles follow the visibility of their user.
    op.execute("""
        CREATE POLICY tenant_isolation ON user_roles
        USING (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id))
        WITH CHECK (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id))
    """)
    # Credentials: a Platform Admin never sees company users' sign-in secrets.
    credential_rule = """
        app_scope() = 'system' OR EXISTS (
            SELECT 1 FROM users u WHERE u.id = user_id AND (
                u.company_id = app_company_id()
                OR (app_scope() = 'platform' AND u.company_id IS NULL)))
    """
    for table in ["refresh_tokens", "mfa_methods", "otp_codes", "recovery_codes"]:
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({credential_rule}) WITH CHECK ({credential_rule})
        """)
    audit_rule = """
        app_scope() = 'system'
        OR (app_scope() = 'platform' AND chain_key = 'platform')
        OR chain_key = app_company_id()::text
    """
    op.execute(f"""
        CREATE POLICY tenant_isolation ON audit_log
        USING ({audit_rule}) WITH CHECK ({audit_rule})
    """)

    # --- Privileges for the application role ---------------------------------------------
    role = _app_role()
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    mutable = ", ".join(t for t in TABLES if t != "audit_log")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {mutable} TO {role}")
    # The audit log is append-only for the application: no UPDATE, no DELETE.
    op.execute(f"GRANT SELECT, INSERT ON audit_log TO {role}")
    op.execute(f"GRANT USAGE ON SEQUENCE audit_log_id_seq TO {role}")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION app_company_id()")
    op.execute("DROP FUNCTION app_scope()")
