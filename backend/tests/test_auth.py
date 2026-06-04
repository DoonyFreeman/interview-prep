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
