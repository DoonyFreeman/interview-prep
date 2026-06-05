"""Auth flow tests: register → login → me, plus failure cases."""
from __future__ import annotations

CREDS = {"email": "user@example.com", "password": "secret123", "display_name": "Tester"}


async def test_register_returns_token(client):
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email_conflicts(client):
    await client.post("/api/auth/register", json=CREDS)
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 409


async def test_login_and_me(client):
    await client.post("/api/auth/register", json=CREDS)
    r = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == CREDS["email"]
    assert me["display_name"] == "Tester"


async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json=CREDS)
    r = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": "wrongpass"}
    )
    assert r.status_code == 401


async def test_me_without_token_unauthorized(client):
    r = await client.get("/api/auth/me")
    assert r.status_code in (401, 403)  # missing bearer


async def test_me_with_garbage_token_unauthorized(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


async def test_register_rejects_short_password(client):
    r = await client.post(
        "/api/auth/register", json={"email": "x@y.com", "password": "123"}
    )
    assert r.status_code == 422


async def test_register_rejects_bad_email(client):
    r = await client.post(
        "/api/auth/register", json={"email": "notanemail", "password": "secret123"}
    )
    assert r.status_code == 422


async def _token(client) -> str:
    await client.post("/api/auth/register", json=CREDS)
    r = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    return r.json()["access_token"]


async def test_me_includes_created_at(client):
    token = await _token(client)
    me = (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).json()
    assert me["created_at"]


async def test_update_display_name(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.patch("/api/auth/me", json={"display_name": "  New Name  "}, headers=h)
    assert r.status_code == 200
    assert r.json()["display_name"] == "New Name"  # trimmed
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert me["display_name"] == "New Name"


async def test_change_password_then_relogin(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/auth/password",
        json={"current_password": CREDS["password"], "new_password": "newsecret456"},
        headers=h,
    )
    assert r.status_code == 204

    # Old password no longer works; new one does.
    old = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/auth/login",
        json={"email": CREDS["email"], "password": "newsecret456"},
    )
    assert new.status_code == 200


async def test_change_password_wrong_current(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/auth/password",
        json={"current_password": "wrongpass", "new_password": "newsecret456"},
        headers=h,
    )
    assert r.status_code == 400


async def test_change_password_rejects_short_new(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/auth/password",
        json={"current_password": CREDS["password"], "new_password": "123"},
        headers=h,
    )
    assert r.status_code == 422


async def test_update_profile_requires_auth(client):
    r = await client.patch("/api/auth/me", json={"display_name": "x"})
    assert r.status_code in (401, 403)
