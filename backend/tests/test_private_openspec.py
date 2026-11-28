from hashlib import sha256
import json

from jose import jwt

from app.config import get_settings
from app.services import private_hr


URL = "/api/cheatsheets/my-openspec"
ORIGINAL = b"%PDF-1.4\nSynthetic original\n%%EOF\n"
BUNDLE = b"%PDF-1.4\nSynthetic bundle\n%%EOF\n"
COMMON = b"%PDF-1.4\nSynthetic common\n%%EOF\n"


async def register(client, email):
    response = await client.post("/api/auth/register", json={
        "email": email,
        "password": "synthetic-test-password",
        "display_name": "Same visible name",
    })
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = await client.get("/api/auth/me", headers=headers)
    assert profile.status_code == 200
    return headers, profile.json()


async def test_private_openspec_downloads_are_independently_account_bound(client, monkeypatch, tmp_path):
    directory = tmp_path / "private-openspec"
    directory.mkdir(mode=0o700)
    common = tmp_path / "common.pdf"
    common.write_bytes(COMMON)
    monkeypatch.setattr(private_hr, "OPENSPEC_DIR", directory)
    monkeypatch.setattr(private_hr, "COMMON_CHEATSHEETS_PDF", common)
    owner, profile = await register(client, "owner@example.com")
    other, _ = await register(client, "other@example.com")  # Same display name.
    uid = profile["id"]
    original = directory / f"{uid}.pdf"
    bundle = directory / f"{uid}.bundle.pdf"
    manifest = directory / f"{uid}.json"
    original.write_bytes(ORIGINAL)
    bundle.write_bytes(BUNDLE)
    for path in (original, bundle):
        path.chmod(0o600)
    record = {
        "owner_email": "owner@example.com",
        "owner_created_at": profile["created_at"],
        "original_sha256": sha256(ORIGINAL).hexdigest(),
        "bundle_sha256": sha256(BUNDLE).hexdigest(),
        "common_sha256": sha256(COMMON).hexdigest(),
    }
    manifest.write_text(json.dumps(record))
    manifest.chmod(0o600)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in (original, bundle, manifest))

    async def flags(headers):
        response = await client.get(URL, headers=headers)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Vary"] == "Authorization"
        return response.json()

    assert await flags(owner) == {"original": True, "bundle": True}
    for suffix, expected, filename in (
        ("/pdf", ORIGINAL, "openspec-agent-engineering.pdf"),
        ("/bundle.pdf", BUNDLE, "my-cheatsheets-all.pdf"),
    ):
        response = await client.get(URL + suffix, headers=owner)
        assert response.content == expected
        assert response.headers["Content-Type"] == "application/pdf"
        assert response.headers["Content-Disposition"] == f'attachment; filename="{filename}"'
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    settings = get_settings()
    legacy = jwt.encode({"sub": str(uid)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    for headers in (other, {"Authorization": f"Bearer {legacy}"}):
        assert await flags(headers) == {"original": False, "bundle": False}
        for suffix in ("/pdf", "/bundle.pdf"):
            response = await client.get(URL + suffix, headers=headers, params={"user_id": uid})
            assert response.status_code == 404 and not response.content
            assert response.headers["Cache-Control"] == "private, no-store"
    for suffix in ("", "/pdf", "/bundle.pdf"):
        assert (await client.get(URL + suffix)).status_code in (401, 403)

    for field in ("original_sha256", "bundle_sha256", "common_sha256"):
        original_ok = field != "original_sha256"
        for invalid in (123, "not-a-hash", "0" * 64):
            manifest.write_text(json.dumps({**record, field: invalid}))
            assert await flags(owner) == {"original": original_ok, "bundle": not original_ok}
            for suffix, allowed, body in (
                ("/pdf", original_ok, ORIGINAL), ("/bundle.pdf", not original_ok, BUNDLE),
            ):
                response = await client.get(URL + suffix, headers=owner)
                assert response.status_code == (200 if allowed else 404)
                assert response.content == (body if allowed else b"")
    for broken in ("{", json.dumps({**record, "owner_email": "other@example.com"})):
        manifest.write_text(broken)
        assert await flags(owner) == {"original": False, "bundle": False}
        for suffix in ("/pdf", "/bundle.pdf"):
            assert (await client.get(URL + suffix, headers=owner)).status_code == 404
    manifest.write_text(json.dumps(record))

    common.write_bytes(COMMON + b"different version")
    assert await flags(owner) == {"original": True, "bundle": False}
    assert (await client.get(URL + "/bundle.pdf", headers=owner)).status_code == 404
    common.write_bytes(COMMON)
    original.write_bytes(ORIGINAL + b"tampered")
    assert await flags(owner) == {"original": False, "bundle": True}
    original.unlink()
    assert (await client.get(URL + "/pdf", headers=owner)).status_code == 404
    assert await flags(owner) == {"original": False, "bundle": True}

    manifest.write_text(json.dumps({**record, "owner_created_at": "2000-01-01T00:00:00"}))
    assert await flags(owner) == {"original": False, "bundle": False}
    manifest.unlink()
    assert await flags(owner) == {"original": False, "bundle": False}
    assert (await client.get(URL + "/bundle.pdf", headers=owner)).status_code == 404
