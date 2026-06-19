"""Pet (corner cat) endpoints: lazy default, partial update, skin clamp, auth.

Pure user-state — no LLM, no content dependency. Mirrors the auth pattern used
across the suite (register → bearer token).
"""
from __future__ import annotations

CREDS = {"email": "pet@example.com", "password": "secret123", "display_name": "Pet"}
CREDS2 = {"email": "pet2@example.com", "password": "secret123", "display_name": "P2"}


async def _auth(client, creds=CREDS) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=creds)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_pet_requires_auth(client):
    assert (await client.get("/api/pet")).status_code == 403
    assert (await client.patch("/api/pet", json={"name": "x"})).status_code == 403


async def test_get_creates_defaults(client):
    headers = await _auth(client)
    r = await client.get("/api/pet", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "name": "",
        "skin": "classic",
        "streak": 0,
        "best_streak": 0,
        "last_active_day": None,
        "hidden": False,
    }


async def test_patch_updates_name_streak_and_visibility(client):
    headers = await _auth(client)
    r = await client.patch(
        "/api/pet",
        headers=headers,
        json={
            "name": "  Мурзик  ",
            "streak": 5,
            "best_streak": 5,
            "last_active_day": "2026-06-19",
            "hidden": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Мурзик"  # trimmed
    assert body["streak"] == 5
    assert body["best_streak"] == 5
    assert body["last_active_day"] == "2026-06-19"
    assert body["hidden"] is True

    # Persisted: a fresh GET sees the same values.
    again = (await client.get("/api/pet", headers=headers)).json()
    assert again == body


async def test_skin_clamped_to_unlocked(client):
    headers = await _auth(client)
    # best_streak 0 → only "classic" unlocked; "void" (needs 30) is rejected.
    r = await client.patch("/api/pet", headers=headers, json={"skin": "void"})
    assert r.json()["skin"] == "classic"

    # Reach the streak that unlocks "tuxedo" (7), then it's accepted.
    await client.patch("/api/pet", headers=headers, json={"streak": 7, "best_streak": 7})
    r = await client.patch("/api/pet", headers=headers, json={"skin": "tuxedo"})
    assert r.json()["skin"] == "tuxedo"


async def test_best_streak_never_below_streak(client):
    headers = await _auth(client)
    r = await client.patch("/api/pet", headers=headers, json={"streak": 9})
    assert r.json()["best_streak"] == 9


async def test_isolated_per_user(client):
    h1 = await _auth(client, CREDS)
    h2 = await _auth(client, CREDS2)
    await client.patch("/api/pet", headers=h1, json={"name": "Alpha", "streak": 3})

    assert (await client.get("/api/pet", headers=h2)).json()["name"] == ""
    assert (await client.get("/api/pet", headers=h1)).json()["name"] == "Alpha"
