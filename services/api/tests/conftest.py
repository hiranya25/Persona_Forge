"""Test setup: a fresh Postgres database, migrated with Alembic, shared by the session.

Needs a Postgres superuser URL in TEST_ADMIN_DATABASE_URL and the roles created by
infra/docker/postgres/init-roles.sh (CI runs that script first).
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL",
                           "postgresql://postgres:postgres@localhost:5432/postgres")
HOST = ADMIN_URL.split("@", 1)[1].rsplit("/", 1)[0]
TEST_DB = "personaforge_test"
SERVICE_DIR = Path(__file__).resolve().parents[1]

os.environ.update({
    "ENVIRONMENT": "test",
    "EMAIL_BACKEND": "memory",
    "DATABASE_URL": f"postgresql+asyncpg://pf_app:pf_app@{HOST}/{TEST_DB}",
    "MIGRATION_DATABASE_URL": f"postgresql+asyncpg://pf_owner:pf_owner@{HOST}/{TEST_DB}",
    "JWT_SECRET": "test-secret-test-secret-test-secret-123",
})
os.environ.pop("REDIS_URL", None)

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from app.core import email  # noqa: E402
from app.core.ratelimit import rate_limiter  # noqa: E402
from app.main import app  # noqa: E402

OWNER_DSN = f"postgresql://pf_owner:pf_owner@{HOST}/{TEST_DB}"
APP_DSN = f"postgresql://pf_app:pf_app@{HOST}/{TEST_DB}"
TABLES = ("audit_log, recovery_codes, otp_codes, mfa_methods, refresh_tokens, "
          "invitations, user_roles, users, companies")


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {TEST_DB} OWNER pf_owner")
    await admin.close()
    # Same schema privileges as infra/docker/postgres/init-roles.sh.
    superuser = await asyncpg.connect(ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}")
    await superuser.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC; "
                            "GRANT ALL ON SCHEMA public TO pf_owner")
    await superuser.close()
    # Alembic's env runs its own event loop, so migrate in a separate process.
    await asyncio.to_thread(subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"],
                            check=True, cwd=SERVICE_DIR)
    yield


@pytest.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    conn = await asyncpg.connect(OWNER_DSN)
    await conn.execute(f"TRUNCATE {TABLES} CASCADE")
    await conn.close()
    email.outbox.clear()
    rate_limiter.reset()
    yield


class Client(httpx.AsyncClient):
    """Test client that behaves like the web app: echoes the CSRF cookie in a header."""

    async def send(self, request: httpx.Request, **kwargs):  # type: ignore[no-untyped-def]
        csrf = self.cookies.get("pf_csrf")
        if csrf and "X-CSRF-Token" not in request.headers:
            request.headers["X-CSRF-Token"] = csrf
        return await super().send(request, **kwargs)


MakeClient = Callable[[], Awaitable[Client]]


@pytest.fixture
async def make_client() -> AsyncIterator[MakeClient]:
    clients: list[Client] = []

    async def factory() -> Client:
        client = Client(transport=httpx.ASGITransport(app=app),
                        base_url="http://testserver/api/v1")
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.aclose()


@pytest.fixture
async def owner_db() -> AsyncIterator[asyncpg.Connection]:
    """Connection as the schema owner (bypasses RLS) - for setup and tamper tests."""
    conn = await asyncpg.connect(OWNER_DSN)
    yield conn
    await conn.close()


@pytest.fixture
async def app_db() -> AsyncIterator[asyncpg.Connection]:
    """Connection as the restricted application role (subject to RLS)."""
    conn = await asyncpg.connect(APP_DSN)
    yield conn
    await conn.close()
