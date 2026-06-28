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


# --- Daily "visit" rollover (atomic, server-authoritative) -----------------
# Bug repro: the streak used to be rolled client-side and pushed via an
# optimistic PATCH that rolled back on any error and never retried. One dropped
# write on a day the user *did* visit left `last_active_day` stale, so two days
# later the gap looked like ≥2 and the streak reset to 1 ("visited every day but
# it reset after day 8"). The fix moves the rollover into a single atomic server
# call: POST /api/pet/visit {today}. These tests pin that contract.


async def test_visit_requires_auth(client):
    assert (
        await client.post("/api/pet/visit", json={"today": "2026-06-20"})
    ).status_code == 403


async def test_visit_first_time_starts_streak(client):
    headers = await _auth(client)
    r = await client.post(
        "/api/pet/visit", headers=headers, json={"today": "2026-06-20"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["streak"] == 1
    assert body["best_streak"] == 1
    assert body["last_active_day"] == "2026-06-20"


async def test_visit_consecutive_days_never_reset(client):
    """The core regression: visiting every day keeps climbing, atomically."""
    headers = await _auth(client)
    for i, day in enumerate(
        ["2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23"], start=1
    ):
        body = (
            await client.post("/api/pet/visit", headers=headers, json={"today": day})
        ).json()
        assert body["streak"] == i, f"day {day} should be streak {i}"
        assert body["last_active_day"] == day


async def test_visit_same_day_is_idempotent(client):
    headers = await _auth(client)
    await client.post("/api/pet/visit", headers=headers, json={"today": "2026-06-20"})
    await client.post("/api/pet/visit", headers=headers, json={"today": "2026-06-21"})
    # Reload the same day twice — no double count.
    a = (
        await client.post(
            "/api/pet/visit", headers=headers, json={"today": "2026-06-21"}
        )
    ).json()
    assert a["streak"] == 2
    assert a["last_active_day"] == "2026-06-21"


async def test_visit_gap_resets_but_keeps_best(client):
    headers = await _auth(client)
    # Climb to 7 (unlocks tuxedo) over 7 consecutive days.
    for n, day in enumerate(
        [f"2026-06-{d:02d}" for d in range(14, 21)], start=1
    ):
        body = (
            await client.post("/api/pet/visit", headers=headers, json={"today": day})
        ).json()
    assert body["streak"] == 7 and body["best_streak"] == 7
    # Skip two days → reset to 1, but best_streak (and unlocked skins) survive.
    after = (
        await client.post(
            "/api/pet/visit", headers=headers, json={"today": "2026-06-23"}
        )
    ).json()
    assert after["streak"] == 1
    assert after["best_streak"] == 7


async def test_visit_persisted(client):
    headers = await _auth(client)
    await client.post("/api/pet/visit", headers=headers, json={"today": "2026-06-20"})
    got = (await client.get("/api/pet", headers=headers)).json()
    assert got["streak"] == 1
    assert got["last_active_day"] == "2026-06-20"
