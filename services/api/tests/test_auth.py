import pyotp

from tests.conftest import MakeClient
from tests.helpers import (
    ADMIN_EMAIL,
    PASSWORD,
    create_user,
    last_code,
    onboard_company,
    platform_admin,
    setup_totp,
    sign_in,
)


async def test_health(make_client: MakeClient) -> None:
    client = await make_client()
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}


async def test_admin_must_set_up_second_factor_then_use_it(make_client: MakeClient) -> None:
    from app.cli import create_platform_admin
    await create_platform_admin(ADMIN_EMAIL, "Owner", PASSWORD)
    client = await make_client()

    first = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert first.json()["status"] == "mfa_setup_required"
    assert "pf_access" not in client.cookies  # no session until a second factor exists

    secret, confirmed = await setup_totp(client, first.json()["mfa_token"])
    assert confirmed["status"] == "ok"
    assert len(confirmed["recovery_codes"]) == 10
    assert (await client.get("/me")).json()["is_platform_admin"] is True

    other = await make_client()
    second = await other.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert second.json()["status"] == "mfa_required"
    assert second.json()["methods"] == ["totp"]
    token = second.json()["mfa_token"]

    wrong = await other.post("/auth/mfa/verify",
                             json={"mfa_token": token, "method": "totp", "code": "000000"})
    assert wrong.status_code == 401
    right = await other.post("/auth/mfa/verify", json={
        "mfa_token": token, "method": "totp", "code": pyotp.TOTP(secret).now()})
    assert right.json()["status"] == "ok"
    assert (await other.get("/me")).status_code == 200


async def test_wrong_password_is_rejected(make_client: MakeClient) -> None:
    await platform_admin(make_client)
    client = await make_client()
    response = await client.post("/auth/login",
                                 json={"email": ADMIN_EMAIL, "password": "not-the-password"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


async def test_recovery_code_forces_new_factor_and_is_single_use(
        make_client: MakeClient) -> None:
    from app.cli import create_platform_admin
    await create_platform_admin(ADMIN_EMAIL, "Owner", PASSWORD)
    client = await make_client()
    first = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    _, confirmed = await setup_totp(client, first.json()["mfa_token"])
    code = confirmed["recovery_codes"][0]

    lost_phone = await make_client()
    login = await lost_phone.post("/auth/login",
                                  json={"email": ADMIN_EMAIL, "password": PASSWORD})
    used = await lost_phone.post("/auth/mfa/verify", json={
        "mfa_token": login.json()["mfa_token"], "method": "recovery_code",
        "code": code.upper()})
    assert used.json()["status"] == "mfa_setup_required"
    _, finished = await setup_totp(lost_phone, used.json()["mfa_token"])
    assert finished["status"] == "ok"
    assert "recovery_codes" not in finished  # nine unused codes remain

    again = await make_client()
    login = await again.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    reused = await again.post("/auth/mfa/verify", json={
        "mfa_token": login.json()["mfa_token"], "method": "recovery_code", "code": code})
    assert reused.status_code == 401


async def test_email_code_as_admin_second_factor(make_client: MakeClient) -> None:
    from app.cli import create_platform_admin
    await create_platform_admin(ADMIN_EMAIL, "Owner", PASSWORD)
    client = await make_client()
    first = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    token = first.json()["mfa_token"]

    started = await client.post("/auth/mfa/setup/email/start", json={"mfa_token": token})
    confirmed = await client.post("/auth/mfa/setup/confirm", json={
        "mfa_token": token, "method_id": started.json()["method_id"],
        "code": last_code(ADMIN_EMAIL)})
    assert confirmed.json()["status"] == "ok"

    other = await make_client()
    login = await other.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert login.json()["methods"] == ["email_otp"]
    token = login.json()["mfa_token"]
    assert (await other.post("/auth/mfa/email/send", json={"mfa_token": token})
            ).status_code == 204
    verified = await other.post("/auth/mfa/verify", json={
        "mfa_token": token, "method": "email_otp", "code": last_code(ADMIN_EMAIL)})
    assert verified.json()["status"] == "ok"


async def test_admin_keeps_at_least_one_second_factor(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    methods = (await admin.get("/me/mfa-methods")).json()
    removed = await admin.delete(f"/me/mfa-methods/{methods[0]['id']}")
    assert removed.status_code == 409


async def test_employee_signs_in_with_password_or_email_code(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])

    with_password = await sign_in(make_client, "analyst@acme.example.com")
    assert (await with_password.get("/me")).json()["roles"] == ["analyst"]

    with_code = await make_client()
    requested = await with_code.post("/auth/otp/request",
                                     json={"email": "analyst@acme.example.com"})
    assert requested.status_code == 202
    verified = await with_code.post("/auth/otp/verify", json={
        "email": "analyst@acme.example.com", "code": last_code("analyst@acme.example.com")})
    assert verified.json()["status"] == "ok"


async def test_admins_cannot_use_email_code_as_only_factor(make_client: MakeClient) -> None:
    from app.core import email
    admin, _ = await platform_admin(make_client)
    await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    email.outbox.clear()

    client = await make_client()
    response = await client.post("/auth/otp/request", json={"email": "boss@acme.example.com"})
    assert response.status_code == 202  # same answer as for anyone else...
    assert email.outbox == []  # ...but no code is sent


async def test_unknown_email_gets_the_same_answer(make_client: MakeClient) -> None:
    client = await make_client()
    response = await client.post("/auth/otp/request", json={"email": "nobody@nowhere.example.com"})
    assert response.status_code == 202


async def test_email_code_locks_after_too_many_attempts(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    client = await make_client()
    await client.post("/auth/otp/request", json={"email": "analyst@acme.example.com"})
    code = last_code("analyst@acme.example.com")
    wrong = "111111" if code != "111111" else "222222"

    for _ in range(5):
        response = await client.post("/auth/otp/verify",
                                     json={"email": "analyst@acme.example.com", "code": wrong})
        assert response.status_code == 401
    locked = await client.post("/auth/otp/verify",
                               json={"email": "analyst@acme.example.com", "code": code})
    assert locked.status_code == 401


async def test_refresh_rotates_and_detects_reuse(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    client = await sign_in(make_client, "analyst@acme.example.com")
    stolen = client.cookies.get("pf_refresh")

    rotated = await client.post("/auth/refresh")
    assert rotated.status_code == 200
    assert client.cookies.get("pf_refresh") != stolen

    attacker = await make_client()
    attacker.cookies.set("pf_refresh", stolen, path="/api/v1/auth")
    attacker.cookies.set("pf_csrf", "x")
    assert (await attacker.post("/auth/refresh")).status_code == 401
    # Reuse revoked the whole session family, including the legitimate new token.
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_logout_ends_the_session(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    client = await sign_in(make_client, "analyst@acme.example.com")
    refresh_token = client.cookies.get("pf_refresh")
    assert (await client.post("/auth/logout")).status_code == 204

    replay = await make_client()
    replay.cookies.set("pf_refresh", refresh_token, path="/api/v1/auth")
    replay.cookies.set("pf_csrf", "x")
    assert (await replay.post("/auth/refresh")).status_code == 401


async def test_state_changes_require_csrf_header(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    response = await admin.post("/admin/companies", json={"name": "Acme"},
                                headers={"X-CSRF-Token": "forged"})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


async def test_change_password(make_client: MakeClient) -> None:
    admin, _ = await platform_admin(make_client)
    company_admin, _ = await onboard_company(make_client, admin, "Acme", "boss@acme.example.com")
    await create_user(company_admin, "analyst@acme.example.com", ["analyst"])
    client = await sign_in(make_client, "analyst@acme.example.com")

    wrong = await client.post("/me/password", json={"current_password": "nope",
                                                    "new_password": "a-new-password-1"})
    assert wrong.status_code == 401
    changed = await client.post("/me/password", json={"current_password": PASSWORD,
                                                      "new_password": "a-new-password-1"})
    assert changed.status_code == 204
    login = await (await make_client()).post(
        "/auth/login", json={"email": "analyst@acme.example.com", "password": "a-new-password-1"})
    assert login.json()["status"] == "ok"


async def test_cli_creates_platform_admin(make_client: MakeClient) -> None:
    """Runs the real command in a fresh process, as an operator would."""
    import asyncio
    import os
    import subprocess
    import sys

    from tests.conftest import SERVICE_DIR

    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "app.cli", "create-platform-admin",
         "--email", ADMIN_EMAIL, "--name", "Owner"],
        cwd=SERVICE_DIR, capture_output=True, text=True,
        env={**os.environ, "PF_ADMIN_PASSWORD": PASSWORD},
    )
    assert result.returncode == 0, result.stderr
    client = await make_client()
    login = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert login.json()["status"] == "mfa_setup_required"
