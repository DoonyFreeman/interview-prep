"""Admin endpoints: env-gated access (ADMIN_EMAILS), per-user stats, pet override."""
from __future__ import annotations

import pytest

from app.config import get_settings

ADMIN = {"email": "admin@example.com", "password": "secret123", "display_name": "Boss"}
USER = {"email": "user@example.com", "password": "secret123", "display_name": "U"}


@pytest.fixture(autouse=True)
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _auth(client, creds) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=creds)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _user_id(client, admin_headers, email: str) -> int:
    users = (await client.get("/api/admin/users", headers=admin_headers)).json()[
        "users"
    ]
    return next(u["id"] for u in users if u["email"] == email)


async def test_admin_routes_reject_anon_and_non_admin(client):
    assert (await client.get("/api/admin/users")).status_code == 403
    headers = await _auth(client, USER)
    assert (await client.get("/api/admin/users", headers=headers)).status_code == 403
    assert (
        await client.get("/api/admin/users/1", headers=headers)
    ).status_code == 403
    assert (
        await client.patch("/api/admin/users/1/pet", headers=headers, json={})
    ).status_code == 403


async def test_me_reports_is_admin(client):
    admin = await _auth(client, ADMIN)
    user = await _auth(client, USER)
    assert (await client.get("/api/auth/me", headers=admin)).json()["is_admin"] is True
    assert (await client.get("/api/auth/me", headers=user)).json()["is_admin"] is False


async def test_list_users_shape(client):
    admin = await _auth(client, ADMIN)
    await _auth(client, USER)
    r = await client.get("/api/admin/users", headers=admin)
    assert r.status_code == 200
    users = r.json()["users"]
    assert [u["email"] for u in users] == [ADMIN["email"], USER["email"]]
    u = users[1]
    assert u["display_name"] == "U"
    assert u["pet"]["streak"] == 0 and u["pet"]["skin"] == "classic"
    assert u["total_concepts"] > 0 and u["mastered_concepts"] == 0
    assert u["total_lessons"] > 0 and u["completed_lessons"] == 0
    assert u["attempts_count"] == 0 and u["avg_score"] == 0
    assert u["tests_total"] > 0 and u["tests_passed"] == 0


async def test_user_detail_includes_progress_and_404(client):
    admin = await _auth(client, ADMIN)
    user_headers = await _auth(client, USER)
    r = await client.post(
        "/api/progress/courses/python-core/lessons/gil",
        headers=user_headers,
        json={"completed": True},
    )
    assert r.status_code == 204

    uid = await _user_id(client, admin, USER["email"])
    r = await client.get(f"/api/admin/users/{uid}", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == USER["email"]
    assert body["user"]["completed_lessons"] == 1
    core = next(c for c in body["progress"]["courses"] if c["slug"] == "python-core")
    gil = next(l for l in core["lessons"] if l["slug"] == "gil")
    assert gil["completed"] is True
    assert "tests" in body

    assert (await client.get("/api/admin/users/9999", headers=admin)).status_code == 404


async def test_admin_pet_override_skips_unlock_clamp(client):
    admin = await _auth(client, ADMIN)
    user_headers = await _auth(client, USER)
    uid = await _user_id(client, admin, USER["email"])

    r = await client.patch(
        f"/api/admin/users/{uid}/pet",
        headers=admin,
        json={
            "streak": 15,
            "best_streak": 17,
            "skin": "golden",
            "hat": "crown",
            "last_active_day": "2026-07-01",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["streak"] == 15 and body["best_streak"] == 17
    # admin write bypasses the unlock clamp (golden needs 60, crown needs 30)
    assert body["skin"] == "golden" and body["hat"] == "crown"

    mine = (await client.get("/api/pet", headers=user_headers)).json()
    assert mine["streak"] == 15 and mine["last_active_day"] == "2026-07-01"

    # best_streak never drops below streak even on an admin write
    r = await client.patch(
        f"/api/admin/users/{uid}/pet", headers=admin, json={"best_streak": 3}
    )
    assert r.json()["best_streak"] == 15
