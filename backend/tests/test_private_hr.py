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


TECHNICAL_URL = "/api/cheatsheets/python-ai-interview/answers"


async def test_technical_answers_are_account_bound_and_uncacheable(client, tmp_path, monkeypatch):
    monkeypatch.setattr(private_hr, "TECHNICAL_INTERVIEW_DIR", tmp_path)
    owner, profile = await register(client, "owner@example.com")
    other, _ = await register(client, "other@example.com")
    answers = {f"synthetic-question-{i}": ANSWER["answer"] + "я" * 500 for i in range(72)}
    record = {
        "owner_email": "owner@example.com",
        "owner_created_at": profile["created_at"],
        "answers": answers,
    }
    path = tmp_path / f"{profile['id']}.json"
    data = json.dumps(record, ensure_ascii=False).encode("utf-8")
    assert len(data) > private_hr.MAX_FILE_BYTES
    path.write_bytes(data)

    response = await client.get(TECHNICAL_URL, headers=owner)
    assert response.status_code == 200
    assert response.json() == answers
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Authorization"

    response = await client.get(f"{TECHNICAL_URL}?user_id={profile['id']}", headers=other)
    assert response.json() == {}
    assert response.headers["Cache-Control"] == "private, no-store"
    response = await client.get(TECHNICAL_URL)
    assert response.status_code in (401, 403)
    assert ANSWER["answer"] not in response.text

    settings = get_settings()
    for claims in ({}, {"account_created_at": "2000-01-01T00:00:00"}):
        legacy_token = jwt.encode(
            {"sub": str(profile["id"]), **claims}, settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        assert (await client.get(TECHNICAL_URL, headers={"Authorization": f"Bearer {legacy_token}"})).json() == {}

    for invalid in (
        {**record, "owner_email": "other@example.com"},
        {**record, "owner_created_at": "2000-01-01T00:00:00"},
        {**record, "answers": {"../../unsafe": ANSWER["answer"]}},
    ):
        path.write_text(json.dumps(invalid))
        assert (await client.get(TECHNICAL_URL, headers=owner)).json() == {}

    path.write_bytes(b"x" * (private_hr.MAX_TECHNICAL_FILE_BYTES + 1))
    assert (await client.get(TECHNICAL_URL, headers=owner)).json() == {}
    path.unlink()
    assert (await client.get(TECHNICAL_URL, headers=owner)).json() == {}


AGENT_GUIDE_URL = "/api/cheatsheets/python-ai-interview/agent-guide"


async def test_agent_guide_shows_only_bound_account_its_structured_sections(client, tmp_path, monkeypatch):
    monkeypatch.setattr(private_hr, "AGENT_GUIDE_DIR", tmp_path)
    owner, profile = await register(client, "owner@example.com")
    other, _ = await register(client, "other@example.com")
    sections = [{"heading": "Synthetic heading", "items": [ANSWER]}]
    record = {
        "owner_email": "owner@example.com",
        "owner_created_at": profile["created_at"],
        "sections": sections,
    }
    path = tmp_path / f"{profile['id']}.json"
    path.write_text(json.dumps(record))

    response = await client.get(AGENT_GUIDE_URL, headers=owner)
    assert response.status_code == 200
    assert response.json() == sections
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Authorization"
    response = await client.get(f"{AGENT_GUIDE_URL}?user_id={profile['id']}", headers=other)
    assert response.json() == []
    assert response.headers["Cache-Control"] == "private, no-store"
    response = await client.get(AGENT_GUIDE_URL)
    assert response.status_code in (401, 403)
    assert ANSWER["answer"] not in response.text

    settings = get_settings()
    token = jwt.encode(
        {"sub": str(profile["id"])}, settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    assert (await client.get(AGENT_GUIDE_URL, headers={"Authorization": f"Bearer {token}"})).json() == []

    for bad_record in (
        {**record, "owner_email": "other@example.com"},
        {**record, "owner_created_at": "2000-01-01T00:00:00"},
        {**record, "sections": [{"heading": "Synthetic heading", "items": []}]},
    ):
        path.write_text(json.dumps(bad_record))
        assert (await client.get(AGENT_GUIDE_URL, headers=owner)).json() == []
    path.unlink()
    assert (await client.get(AGENT_GUIDE_URL, headers=owner)).json() == []


async def test_resume_cheatsheet_stays_inside_its_account(client, tmp_path, monkeypatch):
    monkeypatch.setattr(private_hr, "RESUME_DIR", tmp_path, raising=False)
    owner, profile = await register(client, "resume-owner@example.com")
    other, _ = await register(client, "resume-other@example.com")
    sections = [{
        "id": "first-topic", "title": "Synthetic topic", "quote": "Synthetic quote",
        "panels": [{"title": "Explanation", "text": "Private synthetic explanation"}],
        "scenarios": [{"title": "Success", "steps": [{
            "from_node": "Client", "to_node": "API", "title": "Read",
            "payload": "GET /tasks/42", "state": "Pending", "why": "Fetch a task",
        }]}],
        "questions": [ANSWER],
        "terms": [ANSWER],
    }]
    record = {
        "owner_email": "resume-owner@example.com",
        "owner_created_at": profile["created_at"],
        "sections": sections,
    }
    path = tmp_path / f"{profile['id']}.json"
    path.write_text(json.dumps(record))
    url = "/api/cheatsheets/my-resume"
    response = await client.get(url, headers=owner)
    assert response.status_code == 200
    assert response.json() == sections
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Authorization"
    assert (await client.get(f"{url}?user_id={profile['id']}", headers=other)).json() == []
    assert (await client.get(url)).status_code in (401, 403)

    token = jwt.encode(
        {"sub": str(profile["id"])}, get_settings().jwt_secret, algorithm=get_settings().jwt_algorithm,
    )
    assert (await client.get(url, headers={"Authorization": f"Bearer {token}"})).json() == []
    path.write_text(json.dumps({**record, "owner_email": "different@example.com"}))
    assert (await client.get(url, headers=owner)).json() == []
