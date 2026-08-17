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
