import json

from jose import jwt

from app.config import get_settings
from app.services import private_hr

LESSON = "self-presentation"
PRIVATE_URL = f"/api/hr-screening/answers/{LESSON}"
PUBLIC_URL = f"/api/courses/hr-screening/lessons/{LESSON}"
ANSWER = {"question": "Practice prompt", "answer": "SYNTHETIC_PRIVATE_ANSWER"}


async def register(client, email, display_name="Same visible name"):
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "synthetic-test-password", "display_name": display_name},
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = await client.get("/api/auth/me", headers=headers)
    return headers, profile.json()


async def test_answers_are_only_served_to_owner_and_never_public(client, tmp_path, monkeypatch):
    monkeypatch.setattr(private_hr, "PRIVATE_HR_DIR", tmp_path)
    owner, profile = await register(client, "owner@example.com")
    owner_id = profile["id"]
    other, _ = await register(client, "other@example.com")
    path = tmp_path / f"{owner_id}.json"
    groups = {"self-intro": [ANSWER]}
    path.write_text(json.dumps({
        "owner_email": "owner@example.com",
        "owner_created_at": profile["created_at"],
        "lessons": {LESSON: groups},
    }))

    response = await client.get(PRIVATE_URL, headers=owner)
    assert response.json() == groups
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Authorization"
    settings = get_settings()
    for extra in ({}, {"account_created_at": "2000-01-01T00:00:00"}):
        stale_token = jwt.encode(
            {"sub": str(owner_id), **extra}, settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        stale_header = {"Authorization": f"Bearer {stale_token}"}
        assert (await client.get(PRIVATE_URL, headers=stale_header)).json() == {}
        assert (await client.get("/api/auth/me", headers=stale_header)).status_code == 200

    anonymous = await client.get(PRIVATE_URL)
    assert anonymous.status_code in (401, 403)
    assert ANSWER["answer"] not in anonymous.text
    unauthorised = await client.get(f"{PRIVATE_URL}?user_id={owner_id}", headers=other)
    assert unauthorised.json() == {}
    assert unauthorised.headers["Cache-Control"] == "private, no-store"
    assert (await client.get("/api/hr-screening/answers/behavioral-questions", headers=owner)).json() == {}
    for headers in ({}, owner, other):
        public = await client.get(PUBLIC_URL, headers=headers)
        assert public.status_code == 200
        assert ANSWER["answer"] not in public.text
    search = await client.get("/api/search", params={"q": ANSWER["answer"]}, headers=owner)
    assert search.json()["results"] == []
    slot_search = await client.get("/api/search", params={"q": "self-intro"})
    assert slot_search.json()["results"] == []

    path.unlink()
    assert (await client.get(PRIVATE_URL, headers=owner)).json() == {}


async def test_wrong_owner_and_invalid_file_fail_closed(client, tmp_path, monkeypatch):
    monkeypatch.setattr(private_hr, "PRIVATE_HR_DIR", tmp_path)
    owner, profile = await register(client, "owner@example.com")
    path = tmp_path / f"{profile['id']}.json"
    good = {
        "owner_email": "owner@example.com",
        "owner_created_at": profile["created_at"],
        "lessons": {LESSON: {"self-intro": [ANSWER]}},
    }
    for data in (
        json.dumps({**good, "owner_email": "other@example.com"}),
        json.dumps({**good, "owner_created_at": "2000-01-01T00:00:00"}),
        f'{{"broken": "{ANSWER["answer"]}"',
        "x" * (private_hr.MAX_FILE_BYTES + 1),
    ):
        path.write_text(data)
        response = await client.get(PRIVATE_URL, headers=owner)
        assert response.status_code == 200
        assert response.json() == {}
