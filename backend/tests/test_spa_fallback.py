"""The SPA fallback must serve client routes but never swallow API paths.

`_mount_spa` is a no-op in the normal test run (there is no `app/static/`), so
these tests build the static dir themselves and mount it onto a fresh app —
otherwise the guard would only ever be exercised in a container.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import main


@pytest.fixture
def spa_client(tmp_path, monkeypatch):
    """An app with a stand-in built SPA mounted, as in the Docker image."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (static / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(main, "STATIC_DIR", static)

    app = main.create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_client_routes_fall_back_to_index(spa_client):
    """A deep link hard-refreshed in the browser must render the SPA."""
    async with spa_client as client:
        for path in ("/", "/tests", "/glossary", "/courses/python-core/lessons/gil"):
            r = await client.get(path)
            assert r.status_code == 200, path
            assert "spa" in r.text, path


async def test_real_static_files_are_served(spa_client):
    async with spa_client as client:
        r = await client.get("/favicon.svg")
        assert r.status_code == 200 and r.text == "<svg/>"


async def test_unknown_api_paths_404_instead_of_rendering_the_spa(spa_client):
    """The bug this guards: an unmatched /api/... used to answer 200 text/html,
    so a route that failed to register looked like a working endpoint returning
    unparseable JSON — and a deploy smoke check couldn't tell the difference."""
    async with spa_client as client:
        for path in ("/api/definitely/not/here", "/api/quiz/nope", "/api"):
            r = await client.get(path)
            assert r.status_code == 404, f"{path} -> {r.status_code}"
            assert "text/html" not in r.headers.get("content-type", "")


async def test_registered_api_routes_still_work_with_the_spa_mounted(spa_client):
    """The guard must not shadow the real API: /health and a public endpoint
    still answer normally once the SPA is mounted."""
    async with spa_client as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
        r = await client.get("/api/quiz/tests/topics")
        assert r.status_code == 403  # auth-gated, i.e. the route exists


# --------------------------------------------------------------------------- #
# Cache headers. Without these, browsers cache heuristically off Last-Modified,
# and a stale index.html pins the whole app to the previous release — a deploy
# lands and phones keep showing the old site.
# --------------------------------------------------------------------------- #
async def test_index_is_revalidated_on_every_load(spa_client):
    async with spa_client as client:
        for path in ("/", "/tests", "/courses/python-core/lessons/gil"):
            r = await client.get(path)
            assert r.headers["cache-control"] == "no-cache", path


async def test_hashed_assets_are_cached_immutably(spa_client):
    """Safe precisely because the filename carries a content hash: a new build
    produces a new URL, so a year-long cache can never serve stale code."""
    async with spa_client as client:
        r = await client.get("/assets/app.js")
        assert r.status_code == 200
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_unhashed_static_files_get_a_short_cache(spa_client):
    """Favicons and the manifest keep stable names but do change between
    releases — neither 'forever' nor 'never' is right for them."""
    async with spa_client as client:
        r = await client.get("/favicon.svg")
        assert r.status_code == 200
        assert r.headers["cache-control"] == "public, max-age=3600"


async def test_nested_static_files_are_served(spa_client, tmp_path):
    """Lesson screenshots live in a subfolder of the build (public/lesson-media)."""
    media = tmp_path / "static" / "lesson-media" / "course"
    media.mkdir(parents=True)
    (media / "shot.png").write_bytes(b"PNG")
    r = await spa_client.get("/lesson-media/course/shot.png")
    assert r.status_code == 200
    assert r.content == b"PNG"


@pytest.mark.parametrize(
    "path",
    ["/%2e%2e/secret.txt", "/..%2fsecret.txt", "/lesson-media/%2e%2e/%2e%2e/secret.txt", "abs"],
)
async def test_encoded_dot_segments_cannot_escape_the_static_dir(spa_client, tmp_path, path):
    """The server decodes %2e%2e into "..": without a containment check the
    fallback would read any file the process can (in the image — the SQLite DB)."""
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    (tmp_path / "static" / "lesson-media").mkdir()  # so the old code really walked up
    if path == "abs":  # an encoded absolute path: STATIC_DIR / "/x" == "/x"
        path = "/%2F" + str(tmp_path / "secret.txt").lstrip("/")
    r = await spa_client.get(path)
    assert "TOP-SECRET" not in r.text


@pytest.mark.parametrize("path", ["/%00", "/x%00y"])
async def test_nul_byte_falls_back_instead_of_500(spa_client, path):
    r = await spa_client.get(path)
    assert r.status_code == 200
    assert "<title>spa</title>" in r.text

