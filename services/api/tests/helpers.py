import re

import pyotp

from app.cli import create_platform_admin
from app.core import email
from tests.conftest import Client, MakeClient

ADMIN_EMAIL = "owner@personaforge.example.com"
PASSWORD = "correct-horse-battery"


def last_code(to: str) -> str:
    message = next(m for m in reversed(email.outbox) if m.to == to)
    match = re.search(r"\b(\d{6})\b", message.body)
    assert match, message.body
    return match.group(1)


def last_invite_token(to: str) -> str:
    message = next(m for m in reversed(email.outbox) if m.to == to)
    match = re.search(r"/invite/(\S+)", message.body)
    assert match, message.body
    return match.group(1)


async def setup_totp(client: Client, mfa_token: str | None) -> tuple[str, dict]:
    """Register an authenticator app; returns (secret, confirm response body)."""
    started = await client.post("/auth/mfa/setup/totp/start", json={"mfa_token": mfa_token})
    assert started.status_code == 200, started.text
    secret = started.json()["secret"]
    confirmed = await client.post("/auth/mfa/setup/confirm", json={
        "mfa_token": mfa_token, "method_id": started.json()["method_id"],
        "code": pyotp.TOTP(secret).now()})
    assert confirmed.status_code == 200, confirmed.text
    return secret, confirmed.json()


async def platform_admin(make_client: MakeClient) -> tuple[Client, str]:
    """A signed-in Platform Admin client and its TOTP secret."""
    await create_platform_admin(ADMIN_EMAIL, "Owner", PASSWORD)
    client = await make_client()
    login = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert login.json()["status"] == "mfa_setup_required"
    secret, _ = await setup_totp(client, login.json()["mfa_token"])
    return client, secret


async def onboard_company(make_client: MakeClient, admin: Client, name: str,
                          admin_email: str, **limits: int) -> tuple[Client, str]:
    """Create a company and sign its Company Admin in. Returns (client, company_id)."""
    body: dict = {"name": name}
    if limits:
        body["limits"] = limits
    company = await admin.post("/admin/companies", json=body)
    assert company.status_code == 201, company.text
    company_id = company.json()["id"]
    invited = await admin.post(f"/admin/companies/{company_id}/invite-admin",
                               json={"email": admin_email})
    assert invited.status_code == 201, invited.text

    client = await make_client()
    accepted = await client.post(f"/invitations/{last_invite_token(admin_email)}/accept",
                                 json={"full_name": f"{name} Admin", "password": PASSWORD})
    assert accepted.json()["status"] == "mfa_setup_required", accepted.text
    await setup_totp(client, accepted.json()["mfa_token"])
    return client, company_id


async def create_user(company_admin: Client, user_email: str, roles: list[str]) -> str:
    created = await company_admin.post("/users", json={
        "email": user_email, "full_name": "Team Member", "roles": roles,
        "password": PASSWORD})
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def sign_in(make_client: MakeClient, user_email: str) -> Client:
    client = await make_client()
    login = await client.post("/auth/login", json={"email": user_email, "password": PASSWORD})
    assert login.status_code == 200 and login.json()["status"] == "ok", login.text
    return client
