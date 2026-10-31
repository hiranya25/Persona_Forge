import uuid

import asyncpg

from tests.conftest import MakeClient
from tests.helpers import (
    PASSWORD,
    create_user,
    last_invite_token,
    onboard_company,
    platform_admin,
    sign_in,
)


async def test_onboarding_flow(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, company_id = await onboard_company(make_client, admin, "Acme Capital",
                                                      "boss@acme.example.com")
    me = (await company_admin.get("/me")).json()
    assert me["company"]["id"] == company_id
    assert me["company"]["slug"] == "acme-capital"
    assert me["roles"] == ["company_admin"]

    await create_user(company_admin, "reviewer@acme.example.com", ["reviewer", "viewer"])
    users = (await company_admin.get("/users")).json()
    assert {u["email"] for u in users} == {"boss@acme.example.com", "reviewer@acme.example.com"}

    companies = (await admin.get("/admin/companies")).json()
    assert companies[0]["user_count"] == 2


async def test_invitation_is_single_use(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company = (await admin.post("/admin/companies", json={"name": "Acme"})).json()
    await admin.post(f"/admin/companies/{company['id']}/invite-admin",
                     json={"email": "boss@acme.example.com"})
    token = last_invite_token("boss@acme.example.com")
    client = await make_client()
    info = await client.get(f"/invitations/{token}")
    assert info.json()["company_name"] == "Acme"

    body = {"full_name": "Boss", "password": PASSWORD}
    assert (await client.post(f"/invitations/{token}/accept", json=body)).status_code == 200
    assert (await client.post(f"/invitations/{token}/accept", json=body)).status_code == 404


async def test_reinvite_expires_the_old_link(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company = (await admin.post("/admin/companies", json={"name": "Acme"})).json()
    url = f"/admin/companies/{company['id']}/invite-admin"
    await admin.post(url, json={"email": "boss@acme.example.com"})
    old = last_invite_token("boss@acme.example.com")
    await admin.post(url, json={"email": "boss@acme.example.com"})
    client = await make_client()
    assert (await client.get(f"/invitations/{old}")).status_code == 404
    assert (await client.get(f"/invitations/{last_invite_token('boss@acme.example.com')}")
            ).status_code == 200


async def test_role_checks(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    analyst = await sign_in(make_client, "analyst@acme.example.com")

    assert (await analyst.get("/users")).status_code == 403
    assert (await analyst.get("/audit")).status_code == 403
    assert (await company_admin.get("/admin/companies")).status_code == 403
    assert (await admin.get("/users")).status_code == 403
    assert (await (await make_client()).get("/me")).status_code == 401


async def test_company_admin_cannot_touch_another_company(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    acme_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    globex_admin, _ = await onboard_company(make_client, admin, "Globex", "boss@globex.example.com")
    globex_user = await create_user(globex_admin, "analyst@globex.example.com", ["analyst"])

    visible = {u["email"] for u in (await acme_admin.get("/users")).json()}
    assert visible == {"boss@acme.example.com"}
    patched = await acme_admin.patch(f"/users/{globex_user}", json={"status": "deactivated"})
    assert patched.status_code == 404
    reset = await acme_admin.post(f"/users/{globex_user}/reset-password",
                                  json={"password": "hijacked-password"})
    assert reset.status_code == 404
    audit = (await acme_admin.get("/audit")).json()["items"]
    assert all("globex" not in str(entry["payload"]) for entry in audit)


async def test_row_level_security_blocks_unscoped_queries(
        make_client: MakeClient, app_db: asyncpg.Connection) -> None:
    """Even raw SQL with no WHERE clause only sees the current company's rows."""
    admin, _ = await platform_admin(make_client)
    _, acme_id = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await onboard_company(make_client, admin, "Globex", "boss@globex.example.com")

    async with app_db.transaction():
        await app_db.execute("SELECT set_config('app.scope', 'tenant', true), "
                             "set_config('app.company_id', $1, true)", acme_id)
        emails = {r["email"] for r in await app_db.fetch("SELECT email FROM users")}
        companies = await app_db.fetch("SELECT id FROM companies")
        secrets = await app_db.fetch("SELECT user_id FROM mfa_methods")
    assert emails == {"boss@acme.example.com"}
    assert [str(r["id"]) for r in companies] == [acme_id]
    assert len(secrets) == 1

    async with app_db.transaction():  # no scope set at all: nothing is visible
        assert await app_db.fetch("SELECT id FROM users") == []

    async with app_db.transaction():
        await app_db.execute("SELECT set_config('app.scope', 'platform', true)")
        # The Platform Admin's scope never exposes company users' sign-in secrets.
        rows = await app_db.fetch(
            "SELECT m.id FROM mfa_methods m JOIN users u ON u.id = m.user_id "
            "WHERE u.company_id IS NOT NULL")
    assert rows == []


async def test_tenant_cannot_write_into_another_company(
        make_client: MakeClient, app_db: asyncpg.Connection) -> None:
    admin, _ = await platform_admin(make_client)
    _, acme_id = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    _, globex_id = await onboard_company(make_client, admin, "Globex", "boss@globex.example.com")

    try:
        async with app_db.transaction():
            await app_db.execute("SELECT set_config('app.scope', 'tenant', true), "
                                 "set_config('app.company_id', $1, true)", acme_id)
            await app_db.execute(
                "INSERT INTO users (id, company_id, email, full_name, status) "
                "VALUES ($1, $2, 'mole@globex.example.com', 'Mole', 'active')",
                uuid.uuid4(), uuid.UUID(globex_id))
    except asyncpg.InsufficientPrivilegeError:
        pass
    else:
        raise AssertionError("RLS should reject inserting into another company")


async def test_deactivated_user_loses_access_immediately(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    user_id = await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    analyst = await sign_in(make_client, "analyst@acme.example.com")

    await company_admin.patch(f"/users/{user_id}", json={"status": "deactivated"})
    assert (await analyst.get("/me")).status_code == 401
    assert (await analyst.post("/auth/refresh")).status_code == 401


async def test_role_change_applies_immediately(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    user_id = await create_user(company_admin, "viewer@acme.example.com", ["viewer"])
    viewer = await sign_in(make_client, "viewer@acme.example.com")
    assert (await viewer.get("/audit")).status_code == 200

    await company_admin.patch(f"/users/{user_id}", json={"roles": ["analyst"]})
    assert (await viewer.get("/audit")).status_code == 403


async def test_company_admin_cannot_lock_themselves_out(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    me = (await company_admin.get("/me")).json()["id"]
    assert (await company_admin.patch(f"/users/{me}", json={"status": "deactivated"})
            ).status_code == 409
    assert (await company_admin.patch(f"/users/{me}", json={"roles": ["analyst"]})
            ).status_code == 409


async def test_suspended_company_cannot_sign_in(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, company_id = await onboard_company(make_client, admin, "Acme",
                                                      "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    analyst = await sign_in(make_client, "analyst@acme.example.com")

    await admin.patch(f"/admin/companies/{company_id}", json={"status": "suspended"})
    assert (await analyst.get("/me")).status_code == 403
    login = await (await make_client()).post(
        "/auth/login", json={"email": "analyst@acme.example.com", "password": PASSWORD})
    assert login.status_code == 403


async def test_user_limit_is_enforced(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com",
                                             max_users=2)
    await create_user(company_admin, "one@acme.example.com", ["analyst"])
    response = await company_admin.post("/users", json={
        "email": "two@acme.example.com", "full_name": "Two", "roles": ["analyst"],
        "password": PASSWORD})
    assert response.status_code == 409


async def test_duplicate_email_is_rejected_across_companies(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    acme_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    globex_admin, _ = await onboard_company(make_client, admin, "Globex", "boss@globex.example.com")
    await create_user(acme_admin, "shared@person.example.com", ["analyst"])
    response = await globex_admin.post("/users", json={
        "email": "Shared@Person.example.com", "full_name": "Dup", "roles": ["analyst"],
        "password": PASSWORD})
    assert response.status_code == 409
