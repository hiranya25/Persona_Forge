import asyncpg
import pytest

from tests.conftest import MakeClient
from tests.helpers import create_user, onboard_company, platform_admin


async def test_actions_are_recorded_in_the_right_chain(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])

    platform_actions = [e["action"] for e in (await admin.get("/admin/audit")).json()["items"]]
    assert "company.created" in platform_actions
    assert "company.admin_invited" in platform_actions

    company_actions = [e["action"]
                       for e in (await company_admin.get("/audit")).json()["items"]]
    assert "user.created" in company_actions
    assert "user.invitation_accepted" in company_actions
    assert "company.created" not in company_actions


async def test_audit_pagination(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    for i in range(5):
        await admin.post("/admin/companies", json={"name": f"Company {i}"})
    first = (await admin.get("/admin/audit", params={"limit": 3})).json()
    second = (await admin.get("/admin/audit",
                              params={"limit": 3, "cursor": first["next_cursor"]})).json()
    ids = [e["id"] for e in first["items"] + second["items"]]
    assert ids == sorted(ids, reverse=True)
    assert len(set(ids)) == len(ids)


async def test_verify_detects_tampering(make_client: MakeClient,
                                        owner_db: asyncpg.Connection) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, company_id = await onboard_company(make_client, admin, "Acme",
                                                      "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    assert (await company_admin.post("/audit/verify")).json()["valid"] is True

    # Someone with direct database access quietly edits history.
    target = await owner_db.fetchval(
        "SELECT id FROM audit_log WHERE chain_key = $1 AND action = 'user.created'",
        company_id)
    await owner_db.execute(
        "UPDATE audit_log SET payload = '{\"email\": \"someone-else@acme.example.com\"}' "
        "WHERE id = $1", target)

    result = (await company_admin.post("/audit/verify")).json()
    assert result["valid"] is False
    assert result["first_broken_id"] == target


async def test_verify_detects_deletion(make_client: MakeClient,
                                       owner_db: asyncpg.Connection) -> None:
    admin, _ = await platform_admin(make_client)
    for i in range(3):
        await admin.post("/admin/companies", json={"name": f"Company {i}"})
    middle = await owner_db.fetchval(
        "SELECT id FROM audit_log WHERE chain_key = 'platform' ORDER BY id OFFSET 1 LIMIT 1")
    await owner_db.execute("DELETE FROM audit_log WHERE id = $1", middle)
    assert (await admin.post("/admin/audit/verify")).json()["valid"] is False


async def test_application_role_cannot_rewrite_history(app_db: asyncpg.Connection) -> None:
    async with app_db.transaction():
        await app_db.execute("SELECT set_config('app.scope', 'system', true)")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_db.execute("UPDATE audit_log SET action = 'x'")
    async with app_db.transaction():
        await app_db.execute("SELECT set_config('app.scope', 'system', true)")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_db.execute("DELETE FROM audit_log")
