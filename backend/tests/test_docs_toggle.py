from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def _status(monkeypatch, value: str | None, path: str) -> int:
    if value is None:
        monkeypatch.delenv("API_DOCS", raising=False)
    else:
        monkeypatch.setenv("API_DOCS", value)
    get_settings.cache_clear()
    try:
        return TestClient(create_app()).get(path).status_code
    finally:
        get_settings.cache_clear()


def test_docs_on_by_default(monkeypatch):
    assert _status(monkeypatch, None, "/docs") == 200
    assert _status(monkeypatch, None, "/openapi.json") == 200


def test_docs_off_in_production(monkeypatch):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert _status(monkeypatch, "false", path) == 404
